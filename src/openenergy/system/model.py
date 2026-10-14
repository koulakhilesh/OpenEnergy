"""System dispatch: what runs each hour, at what cost, and the price it implies."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import numpy as np
import numpy.typing as npt
import pandas as pd

from openenergy.data.series import _validate
from openenergy.errors import ConfigError, DataError

if TYPE_CHECKING:
    from openenergy.system.commitment import Commitment

Backend = Literal["auto", "merit", "pypsa"]
PriceKind = Literal["marginal", "start"]
RENEWABLES = frozenset({"wind", "solar"})
DEFAULT_VOLL = 6000.0


@dataclass(frozen=True, eq=False)
class Generator:
    """One generator or tranche: available MW and marginal cost (GBP/MWh) per snapshot.

    ``must_run`` units produce exactly their available output (historic profiles).
    ``emissions_t_per_mwh`` is tCO2 per MWh of electricity.
    """

    name: str
    technology: str
    capacity_mw: pd.Series[float] = field(repr=False)
    marginal_cost: pd.Series[float] = field(repr=False)
    must_run: bool = False
    emissions_t_per_mwh: float = 0.0


@dataclass(frozen=True)
class Storage:
    """Storage optimised in the dispatch; ``efficiency`` is round trip."""

    name: str
    power_mw: float
    hours: float
    efficiency: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.power_mw) and self.power_mw > 0):
            raise ConfigError(f"{self.name}: power_mw must be positive, got {self.power_mw}")
        if not (math.isfinite(self.hours) and self.hours > 0):
            raise ConfigError(f"{self.name}: hours must be positive, got {self.hours}")
        if not 0 < self.efficiency <= 1:
            raise ConfigError(f"{self.name}: efficiency must be in (0, 1], got {self.efficiency}")


@dataclass(frozen=True, eq=False)
class Link:
    """A price-taking interconnector to a neighbouring market.

    It imports when GB's price is above ``price`` (the neighbour's, GBP/MWh) and exports
    when below, up to ``import_mw`` and ``export_mw`` in each snapshot. ``hurdle`` (GBP/MWh)
    is added to imports and taken off exports (losses and trading costs).
    """

    name: str
    import_mw: pd.Series[float] = field(repr=False)
    export_mw: pd.Series[float] = field(repr=False)
    price: pd.Series[float] = field(repr=False)
    hurdle: float = 0.0


@dataclass(frozen=True, eq=False)
class SystemSpec:
    """Demand (MW), generators, storage and links on one bus, all on the demand's UTC index."""

    demand: pd.Series[float] = field(repr=False)
    generators: tuple[Generator, ...]
    storage: tuple[Storage, ...] = ()
    voll: float = DEFAULT_VOLL
    links: tuple[Link, ...] = ()
    step: pd.Timedelta = field(init=False)

    def __post_init__(self) -> None:
        demand, step = _validate(self.demand)
        if demand.isna().any():
            raise DataError("demand has missing values")
        if (demand < 0).any():
            raise DataError("demand must be non-negative")
        if not self.generators:
            raise ConfigError("a system needs at least one generator")
        names = (
            [g.name for g in self.generators]
            + [s.name for s in self.storage]
            + [link.name for link in self.links]
        )
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ConfigError(f"duplicate names: {', '.join(duplicates)}")
        for gen in self.generators:
            for label, series in (
                ("capacity_mw", gen.capacity_mw),
                ("marginal_cost", gen.marginal_cost),
            ):
                if not series.index.equals(demand.index):
                    raise DataError(f"{gen.name}: {label} must share the demand index")
                if series.isna().any():
                    raise DataError(f"{gen.name}: {label} has missing values")
            if (gen.capacity_mw < 0).any():
                raise DataError(f"{gen.name}: capacity_mw must be non-negative")
        for link in self.links:
            for label, series in (
                ("import_mw", link.import_mw),
                ("export_mw", link.export_mw),
                ("price", link.price),
            ):
                if not series.index.equals(demand.index):
                    raise DataError(f"{link.name}: {label} must share the demand index")
                if series.isna().any():
                    raise DataError(f"{link.name}: {label} has missing values")
            if (link.import_mw < 0).any() or (link.export_mw < 0).any():
                raise DataError(f"{link.name}: import_mw and export_mw must be non-negative")
            if not (math.isfinite(link.hurdle) and link.hurdle >= 0):
                raise ConfigError(f"{link.name}: hurdle must be non-negative")
        if not (math.isfinite(self.voll) and self.voll > 0):
            raise ConfigError(f"voll must be positive, got {self.voll}")
        object.__setattr__(self, "demand", demand)
        object.__setattr__(self, "step", step)

    @property
    def step_hours(self) -> float:
        return float(self.step / pd.Timedelta(hours=1))

    def must_run_mw(self) -> pd.Series[float]:
        total = pd.Series(0.0, index=self.demand.index)
        for gen in self.generators:
            if gen.must_run:
                total = total + gen.capacity_mw
        return total

    def export_mw(self) -> pd.Series[float]:
        total = pd.Series(0.0, index=self.demand.index)
        for link in self.links:
            total = total + link.export_mw
        return total


@dataclass(frozen=True, eq=False)
class SystemResult:
    """Dispatch outcome. Power in MW per snapshot; ``storage`` is net discharge.

    Unit commitment adds ``start_price`` (marginal price including start costs),
    ``units_online`` and ``starts`` per committed tranche. With links, ``links`` holds each
    link's net flow (MW, positive into GB).
    """

    price: pd.Series[float]
    generation: pd.DataFrame
    storage: pd.DataFrame
    unserved: pd.Series[float]
    curtailment: pd.Series[float]
    emissions_t: pd.Series[float]
    cost: float
    backend: str
    technologies: dict[str, str]
    start_price: pd.Series[float] | None = None
    units_online: pd.DataFrame | None = None
    starts: pd.DataFrame | None = None
    links: pd.DataFrame | None = None

    def by_technology(self) -> pd.DataFrame:
        """Generation summed by technology, plus storage, net imports and unserved energy."""
        grouped = self.generation.T.groupby(pd.Series(self.technologies)).sum().T
        if not self.storage.empty:
            grouped["storage"] = self.storage.sum(axis=1)
        if self.links is not None and not self.links.empty:
            grouped["interconnectors"] = self.links.sum(axis=1)
        grouped["unserved"] = self.unserved
        return grouped

    def price_of(self, kind: PriceKind) -> pd.Series[float]:
        """The marginal price, or (unit commitment only) the price including start costs."""
        if kind == "marginal":
            return self.price
        if self.start_price is None:
            raise ConfigError("the start-cost price needs unit commitment")
        return self.start_price


def solve(
    spec: SystemSpec, backend: Backend = "auto", commitment: Commitment | None = None
) -> SystemResult:
    """Dispatch ``spec`` at least cost.

    Without storage every hour is independent and the merit order is the exact optimum,
    so ``auto`` uses it; with storage ``auto`` uses PyPSA (``pip install openenergy[system]``).
    With ``commitment``, thermal units have start-up costs and minimum stable output and days
    are solved in turn with a lookahead (storage included). The merit order and unit
    commitment dispatch links as two generators each (see ``_flatten_links``), which gives
    the same prices as PyPSA's links.
    """
    _check_must_run(spec)
    if commitment is not None:
        if backend != "auto":
            raise ConfigError("unit commitment has its own solver; leave backend as 'auto'")
        from openenergy.system.commitment import commit

        if spec.links:
            return _restore_links(spec, commit(_flatten_links(spec), commitment))
        return commit(spec, commitment)
    if backend == "auto":
        backend = "pypsa" if spec.storage else "merit"
    if backend == "merit":
        if spec.storage:
            raise ConfigError("the merit-order backend cannot dispatch storage; use 'pypsa'")
        from openenergy.system.merit import merit_order

        if spec.links:
            return _restore_links(spec, merit_order(_flatten_links(spec)))
        return merit_order(spec)
    if backend == "pypsa":
        from openenergy.system._pypsa import dispatch

        return dispatch(spec)
    raise ConfigError(f"backend must be 'auto', 'merit' or 'pypsa', got {backend!r}")


def _check_must_run(spec: SystemSpec) -> None:
    excess = spec.must_run_mw() - spec.demand - spec.export_mw()
    over = excess > 1e-6
    if over.any():
        raise DataError(
            f"must-run output exceeds demand in {int(over.sum())} periods "
            f"(by up to {excess.max():.0f} MW); reduce must-run scaling"
        )


_LINK_IN = ":import"
_LINK_UNUSED = ":export_unused"


def _flatten_links(spec: SystemSpec) -> SystemSpec:
    """Each link as generators: imports at the neighbour's price plus hurdle, and export
    capacity left unused at the neighbour's price minus hurdle, with demand raised by the
    export capacity. Minimising cost then maximises export revenue; prices are unchanged.
    """
    generators = list(spec.generators)
    demand = spec.demand
    for link in spec.links:
        generators.append(
            Generator(f"{link.name}{_LINK_IN}", "link", link.import_mw, link.price + link.hurdle)
        )
        generators.append(
            Generator(
                f"{link.name}{_LINK_UNUSED}", "link", link.export_mw, link.price - link.hurdle
            )
        )
        demand = demand + link.export_mw
    return SystemSpec(demand.rename(None), tuple(generators), spec.storage, spec.voll)


def _restore_links(spec: SystemSpec, flat: SystemResult) -> SystemResult:
    """Net link flows (positive into GB) and the true cost from a flattened result."""
    names = [g.name for g in spec.generators]
    flows = pd.DataFrame(
        {
            link.name: flat.generation[f"{link.name}{_LINK_IN}"]
            - (link.export_mw - flat.generation[f"{link.name}{_LINK_UNUSED}"])
            for link in spec.links
        },
        index=spec.demand.index,
    )
    # The flattened objective counts all export capacity at its value; take that back out.
    offered = sum(float((link.export_mw * (link.price - link.hurdle)).sum()) for link in spec.links)
    return dataclasses.replace(
        flat,
        generation=flat.generation[names],
        technologies={g.name: g.technology for g in spec.generators},
        cost=flat.cost - offered * spec.step_hours,
        links=flows,
    )


def result_frames(
    spec: SystemSpec, dispatch: npt.NDArray[np.float64]
) -> tuple[pd.DataFrame, pd.Series[float], pd.Series[float]]:
    """Generation frame, renewable curtailment and emissions from a T x G dispatch array."""
    index = spec.demand.index
    generation = pd.DataFrame(dispatch, index=index, columns=[g.name for g in spec.generators])
    curtailment = pd.Series(0.0, index=index)
    emissions = pd.Series(0.0, index=index)
    for gen in spec.generators:
        if gen.technology in RENEWABLES:
            curtailment += (gen.capacity_mw - generation[gen.name]).clip(lower=0.0)
        emissions += generation[gen.name] * gen.emissions_t_per_mwh * spec.step_hours
    return generation, curtailment, emissions
