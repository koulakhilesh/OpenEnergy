"""PyPSA backend: the only module that imports PyPSA (``pip install openenergy[system]``)."""

from __future__ import annotations

import logging
import math
import warnings
from typing import Any

import numpy as np
import pandas as pd

from openenergy.errors import ConfigError, DispatchError
from openenergy.system.model import SystemResult, SystemSpec, result_frames

BUS = "GB"
_UNSERVED = "__unserved"
_QUIET = ("pypsa", "linopy")


def dispatch(spec: SystemSpec) -> SystemResult:
    """Least-cost dispatch with storage as one linear programme over all periods.

    Storage sees every period at once (perfect foresight) and returns to its starting
    state of charge at the end, so results are an idealised benchmark.
    """
    try:
        import pypsa
    except ImportError as exc:
        raise ConfigError(
            "the PyPSA backend needs the system extra: pip install 'openenergy[system]'"
        ) from exc

    levels = {name: logging.getLogger(name).level for name in _QUIET}
    for name in _QUIET:
        logging.getLogger(name).setLevel(logging.ERROR)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            network = _network(pypsa, spec)
            # The LP-file route applies output_flag before HiGHS loads the model; the
            # direct API prints the HiGHS banner first.
            status, condition = network.optimize(
                solver_name="highs",
                io_api="lp",
                progress=False,
                include_objective_constant=False,
                output_flag=False,
            )
    finally:
        for name, level in levels.items():
            logging.getLogger(name).setLevel(level)
    if status != "ok":
        raise DispatchError(f"PyPSA could not solve the system: {status} ({condition})")

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
        capacity = gen.capacity_mw.to_numpy(dtype=np.float64)
        p_nom = float(capacity.max())
        available = capacity / p_nom if p_nom > 0 else np.zeros_like(capacity)
        network.add(
            "Generator",
            gen.name,
            bus=BUS,
            p_nom=max(p_nom, 1.0),
            p_max_pu=pd.Series(available, index=snapshots),
            p_min_pu=pd.Series(available if gen.must_run else 0.0, index=snapshots),
            marginal_cost=_values(gen.marginal_cost, snapshots),
        )
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
    return network


def _values(series: pd.Series[float], snapshots: pd.DatetimeIndex) -> pd.Series[float]:
    return pd.Series(series.to_numpy(dtype=np.float64), index=snapshots)
