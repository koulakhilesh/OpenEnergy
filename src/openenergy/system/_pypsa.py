"""PyPSA backend: the only module that imports PyPSA (``pip install openenergy[system]``)."""

from __future__ import annotations

import logging
import math
import warnings
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

import numpy as np
import pandas as pd

from openenergy.errors import ConfigError, DispatchError
from openenergy.system.model import Generator, SystemResult, SystemSpec, result_frames

BUS = "GB"
_UNSERVED = "__unserved"
_IMPORT = "__import"
_EXPORT = "__export"
_QUIET = ("pypsa", "linopy")


def dispatch(spec: SystemSpec) -> SystemResult:
    """Least-cost dispatch with storage as one linear programme over all periods.

    Storage sees every period at once (perfect foresight) and returns to its starting
    state of charge at the end, so results are an idealised benchmark.
    """
    pypsa = _pypsa()
    with _quiet():
        network = _network(pypsa, spec)
    _optimise(network, "the system")

    index = spec.demand.index
    names = [g.name for g in spec.generators]
    p = network.generators_t.p
    dispatch_mw = p[names].to_numpy(dtype=np.float64)
    generation, curtailment, emissions = result_frames(spec, dispatch_mw)
    storage = pd.DataFrame(
        {
            s.name: network.storage_units_t.p[s.name].to_numpy(dtype=np.float64)
            for s in spec.storage
        },
        index=index,
    )
    price = network.buses_t.marginal_price[BUS].to_numpy(dtype=np.float64)
    # Solver round-off leaves duals like -1e-12 in hours set by free wind.
    price = np.where(np.abs(price) < 1e-9, 0.0, price)
    links = None
    if spec.links:
        links = pd.DataFrame(
            {
                link.name: (
                    p[f"{link.name}{_IMPORT}"].to_numpy(dtype=np.float64)
                    + p[f"{link.name}{_EXPORT}"].to_numpy(dtype=np.float64)
                )
                for link in spec.links
            },
            index=index,
        )
    return SystemResult(
        price=pd.Series(price, index=index),
        generation=generation,
        storage=storage,
        unserved=pd.Series(p[_UNSERVED].to_numpy(dtype=np.float64), index=index),
        curtailment=curtailment,
        emissions_t=emissions,
        cost=float(network.objective),
        backend="pypsa",
        technologies={g.name: g.technology for g in spec.generators},
        links=links,
    )


def _network(pypsa: Any, spec: SystemSpec) -> Any:
    snapshots = pd.DatetimeIndex(spec.demand.index).tz_convert(None)
    network = pypsa.Network()
    network.set_snapshots(snapshots)
    network.snapshot_weightings.loc[:, :] = spec.step_hours
    network.add("Carrier", "AC")
    network.add("Bus", BUS, carrier="AC")
    network.add("Load", "demand", bus=BUS, p_set=_values(spec.demand, snapshots))
    for gen in spec.generators:
        _add_generator(network, gen.name, BUS, gen, 1.0, snapshots)
    network.add(
        "Generator",
        _UNSERVED,
        bus=BUS,
        p_nom=float(spec.demand.max()) + 1.0,
        marginal_cost=spec.voll,
    )
    for unit in spec.storage:
        one_way = math.sqrt(unit.efficiency)
        network.add(
            "StorageUnit",
            unit.name,
            bus=BUS,
            p_nom=unit.power_mw,
            max_hours=unit.hours,
            efficiency_store=one_way,
            efficiency_dispatch=one_way,
            cyclic_state_of_charge=True,
        )
    for link in spec.links:
        # A neighbour is a price taker: imports cost its price, exports earn it.
        for suffix, limit, sign, cost in (
            (_IMPORT, link.import_mw, 1.0, link.price + link.hurdle),
            (_EXPORT, link.export_mw, -1.0, link.price - link.hurdle),
        ):
            values = limit.to_numpy(dtype=np.float64)
            p_nom = max(float(values.max()), 1.0)
            share = pd.Series(values / p_nom, index=snapshots)
            network.add(
                "Generator",
                f"{link.name}{suffix}",
                bus=BUS,
                p_nom=p_nom,
                p_max_pu=share if sign > 0 else 0.0,
                p_min_pu=0.0 if sign > 0 else -share,
                marginal_cost=_values(cost, snapshots),
            )
    return network


def dispatch_two_zones(
    spec: SystemSpec,
    zones: tuple[str, str],
    first_share: Mapping[str, float],
    first_demand_share: pd.Series[float],
    limit_mw: pd.Series[float],
) -> pd.DataFrame:
    """Least-cost dispatch of ``spec`` (no storage or links) on two buses joined by one link.

    Demand and each technology's generators are split by the first zone's share; the link
    carries up to ``limit_mw`` either way. Returns each zone's price (``price_<zone>``) and
    the flow from the first zone to the second (``transfer_mw``).
    """
    if spec.storage or spec.links:
        raise ConfigError("two zones support the historic system only (no storage or links)")
    pypsa = _pypsa()
    snapshots = pd.DatetimeIndex(spec.demand.index).tz_convert(None)
    demand = spec.demand.to_numpy(dtype=np.float64)
    first = demand * first_demand_share.to_numpy(dtype=np.float64)
    with _quiet():
        network = pypsa.Network()
        network.set_snapshots(snapshots)
        network.snapshot_weightings.loc[:, :] = spec.step_hours
        network.add("Carrier", "AC")
        for zone, load in zip(zones, (first, demand - first), strict=True):
            network.add("Bus", zone, carrier="AC")
            network.add("Load", f"demand_{zone}", bus=zone, p_set=pd.Series(load, snapshots))
            network.add(
                "Generator",
                f"{_UNSERVED}_{zone}",
                bus=zone,
                p_nom=float(load.max()) + 1.0,
                marginal_cost=spec.voll,
            )
        for gen in spec.generators:
            if gen.technology not in first_share:
                raise ConfigError(f"no zone share for {gen.technology}")
            share = first_share[gen.technology]
            for zone, part in zip(zones, (share, 1 - share), strict=True):
                if part > 0:
                    _add_generator(network, f"{gen.name}_{zone}", zone, gen, part, snapshots)
        peak = float(limit_mw.max())
        capability = pd.Series(limit_mw.to_numpy(dtype=np.float64) / peak, index=snapshots)
        network.add(
            "Link",
            "boundary",
            bus0=zones[0],
            bus1=zones[1],
            p_nom=peak,
            p_max_pu=capability,
            p_min_pu=-capability,
        )
    _optimise(network, "the two zones")
    prices = network.buses_t.marginal_price
    frame = {f"price_{zone}": prices[zone].to_numpy(dtype=np.float64) for zone in zones}
    frame["transfer_mw"] = network.links_t.p0["boundary"].to_numpy(dtype=np.float64)
    return pd.DataFrame(frame, index=spec.demand.index)


def _pypsa() -> Any:
    try:
        import pypsa
    except ImportError as exc:
        raise ConfigError(
            "the PyPSA backend needs the system extra: pip install 'openenergy[system]'"
        ) from exc
    return pypsa


@contextmanager
def _quiet() -> Iterator[None]:
    """Silence PyPSA's and linopy's logging and pandas' future warnings."""
    levels = {name: logging.getLogger(name).level for name in _QUIET}
    for name in _QUIET:
        logging.getLogger(name).setLevel(logging.ERROR)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            yield
    finally:
        for name, level in levels.items():
            logging.getLogger(name).setLevel(level)


def _optimise(network: Any, what: str) -> None:
    with _quiet():
        # The LP-file route applies output_flag before HiGHS loads the model; the direct
        # API prints the HiGHS banner first.
        status, condition = network.optimize(
            solver_name="highs",
            io_api="lp",
            progress=False,
            include_objective_constant=False,
            output_flag=False,
        )
    if status != "ok":
        raise DispatchError(f"PyPSA could not solve {what}: {status} ({condition})")


def _add_generator(
    network: Any, name: str, bus: str, gen: Generator, share: float, snapshots: pd.DatetimeIndex
) -> None:
    """``share`` of ``gen``'s available capacity on ``bus``."""
    capacity = gen.capacity_mw.to_numpy(dtype=np.float64) * share
    p_nom = float(capacity.max())
    available = capacity / p_nom if p_nom > 0 else np.zeros_like(capacity)
    network.add(
        "Generator",
        name,
        bus=bus,
        p_nom=max(p_nom, 1.0),
        p_max_pu=pd.Series(available, index=snapshots),
        p_min_pu=pd.Series(available if gen.must_run else 0.0, index=snapshots),
        marginal_cost=_values(gen.marginal_cost, snapshots),
    )


def _values(series: pd.Series[float], snapshots: pd.DatetimeIndex) -> pd.Series[float]:
    return pd.Series(series.to_numpy(dtype=np.float64), index=snapshots)
