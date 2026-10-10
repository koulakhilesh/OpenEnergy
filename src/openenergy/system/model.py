"""System dispatch: what runs each hour, at what cost, and the price it implies."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from openenergy.data.series import _validate
from openenergy.errors import ConfigError, DataError

Backend = Literal["auto", "merit", "pypsa"]
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
class SystemSpec:
    """Demand (MW), generators and storage on one bus, all on the demand's UTC index."""

    demand: pd.Series[float] = field(repr=False)
    generators: tuple[Generator, ...]
    storage: tuple[Storage, ...] = ()
    voll: float = DEFAULT_VOLL
    step: pd.Timedelta = field(init=False)

    def __post_init__(self) -> None:
        demand, step = _validate(self.demand)
        if demand.isna().any():
            raise DataError("demand has missing values")
        if (demand < 0).any():
            raise DataError("demand must be non-negative")
        if not self.generators:
            raise ConfigError("a system needs at least one generator")
        names = [g.name for g in self.generators] + [s.name for s in self.storage]
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


@dataclass(frozen=True, eq=False)
class SystemResult:
    """Dispatch outcome. Power in MW per snapshot; ``storage`` is net discharge."""

    price: pd.Series[float]
    generation: pd.DataFrame
    storage: pd.DataFrame
    unserved: pd.Series[float]
    curtailment: pd.Series[float]
    emissions_t: pd.Series[float]
    cost: float
    backend: str
    technologies: dict[str, str]

    def by_technology(self) -> pd.DataFrame:
        """Generation summed by technology, plus storage and unserved energy."""
        grouped = self.generation.T.groupby(pd.Series(self.technologies)).sum().T
        if not self.storage.empty:
            grouped["storage"] = self.storage.sum(axis=1)
        grouped["unserved"] = self.unserved
        return grouped


def solve(spec: SystemSpec, backend: Backend = "auto") -> SystemResult:
    """Dispatch ``spec`` at least cost.

    Without storage every hour is independent and the merit order is the exact optimum,
    so ``auto`` uses it; with storage ``auto`` uses PyPSA (``pip install openenergy[system]``).
    """
    _check_must_run(spec)
    if backend == "auto":
        backend = "pypsa" if spec.storage else "merit"
    if backend == "merit":
        if spec.storage:
            raise ConfigError("the merit-order backend cannot dispatch storage; use 'pypsa'")
        from openenergy.system.merit import merit_order

        return merit_order(spec)
    if backend == "pypsa":
        from openenergy.system._pypsa import dispatch

        return dispatch(spec)
    raise ConfigError(f"backend must be 'auto', 'merit' or 'pypsa', got {backend!r}")


def _check_must_run(spec: SystemSpec) -> None:
    excess = spec.must_run_mw() - spec.demand
    over = excess > 1e-6
    if over.any():
        raise DataError(
            f"must-run output exceeds demand in {int(over.sum())} periods "
            f"(by up to {excess.max():.0f} MW); reduce must-run scaling"
        )


def result_frames(
    spec: SystemSpec, dispatch: np.ndarray[tuple[int, int], np.dtype[np.float64]]
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
