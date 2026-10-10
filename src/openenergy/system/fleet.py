"""Build a GB system from the generation mix, fleet data and stated assumptions."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from openenergy.data.fleet import EMISSION_FACTORS, SystemInputs
from openenergy.errors import ConfigError, DataError
from openenergy.system.model import DEFAULT_VOLL, Generator, Storage, SystemSpec

# Historic output held fixed: no open data to model imports or plant-level constraints.
# Keys are technology names, values the generation-mix columns.
FIXED_PROFILES = {
    "nuclear": "nuclear",
    "biomass": "biomass",
    "hydro": "hydro",
    "imports": "imports",
    "other": "other",
    "pumped_storage": "storage",
}
RENEWABLE_PROFILES = {"wind": ("wind", "wind_emb"), "solar": ("solar",)}
SCALABLE = (*FIXED_PROFILES, *RENEWABLE_PROFILES)
THERMAL_GROUPS = ("ccgt", "coal", "peaking")
FUEL_OF = {"ccgt": "gas", "coal": "coal", "peaking": "gas"}


@dataclass(frozen=True)
class FleetAssumptions:
    """Stated, configurable modelling assumptions; none is fitted to prices.

    Each thermal group is split into ``tranches`` of equal size whose efficiencies spread
    evenly over the fleet average plus or minus the spread (fractions, e.g. 0.04 = 4 pp).
    Peaking plant (gas turbines and oil engines) is one tranche costed as gas.
    """

    tranches: int = 5
    availability: float = 0.9
    ccgt_spread: float = 0.04
    coal_spread: float = 0.02
    peaking_efficiency: float = 0.35
    variable_cost: float = 0.0

    def __post_init__(self) -> None:
        if self.tranches < 1:
            raise ConfigError(f"tranches must be at least 1, got {self.tranches}")
        if not 0 < self.availability <= 1:
            raise ConfigError(f"availability must be in (0, 1], got {self.availability}")
        for name in ("ccgt_spread", "coal_spread"):
            value = getattr(self, name)
            if not 0 <= value < 0.2:
                raise ConfigError(f"{name} must be in [0, 0.2), got {value}")
        if not 0 < self.peaking_efficiency <= 1:
            raise ConfigError(
                f"peaking_efficiency must be in (0, 1], got {self.peaking_efficiency}"
            )
        if not (math.isfinite(self.variable_cost) and self.variable_cost >= 0):
            raise ConfigError(f"variable_cost must be non-negative, got {self.variable_cost}")


@dataclass(frozen=True)
class Adjustments:
    """Scenario changes to the historic system.

    ``scale`` multiplies historic profiles (wind, solar, nuclear, imports, ...);
    ``capacity_mw`` replaces installed thermal capacity (ccgt, coal, peaking);
    ``fuel_price_scale`` multiplies gas or coal prices; ``eu_ets_gbp_per_t`` replaces the
    EU ETS price; ``carbon_price_support`` keeps or removes the GB top-up.
    """

    scale: Mapping[str, float] = field(default_factory=dict)
    capacity_mw: Mapping[str, float] = field(default_factory=dict)
    fuel_price_scale: Mapping[str, float] = field(default_factory=dict)
    eu_ets_gbp_per_t: float | None = None
    carbon_price_support: bool = True

    def __post_init__(self) -> None:
        _check_keys("scale", self.scale, SCALABLE)
        _check_keys("capacity_mw", self.capacity_mw, THERMAL_GROUPS)
        _check_keys("fuel_price_scale", self.fuel_price_scale, ("gas", "coal"))
        if self.eu_ets_gbp_per_t is not None:
            _check_non_negative("eu_ets_gbp_per_t", self.eu_ets_gbp_per_t)


def thermal_generators(
    index: pd.DatetimeIndex,
    inputs: SystemInputs,
    assumptions: FleetAssumptions | None = None,
    adjustments: Adjustments | None = None,
) -> list[Generator]:
    """CCGT, coal and peaking tranches with short-run marginal cost (GBP/MWh) per period."""
    assumptions = assumptions or FleetAssumptions()
    adjustments = adjustments or Adjustments()
    years = set(index.year)
    if len(years) != 1:
        raise DataError(f"build one calendar year at a time, got {sorted(years)}")
    efficiency = inputs.efficiency(years.pop())
    capacity = inputs.capacity(index)
    installed = {
        "ccgt": capacity["ccgt_mw"],
        "coal": capacity["coal_mw"],
        "peaking": capacity["gas_turbine_mw"] + capacity["oil_engine_mw"],
    }
    fuel = inputs.fuel_prices(index)
    carbon = inputs.carbon_prices(index)
    eu_ets = (
        carbon["eu_ets_gbp_per_t"]
        if adjustments.eu_ets_gbp_per_t is None
        else pd.Series(adjustments.eu_ets_gbp_per_t, index=index)
    )
    support = 1.0 if adjustments.carbon_price_support else 0.0

    generators = []
    for group in THERMAL_GROUPS:
        fuel_name = FUEL_OF[group]
        mw = installed[group]
        if group in adjustments.capacity_mw:
            mw = pd.Series(float(adjustments.capacity_mw[group]), index=index)
        fuel_cost = (
            fuel[fuel_name] * adjustments.fuel_price_scale.get(fuel_name, 1.0)
            + support * carbon[f"cps_{fuel_name}"]
            + eu_ets * EMISSION_FACTORS[fuel_name]
        )
        for k, eta in enumerate(_efficiencies(group, efficiency, assumptions)):
            share = 1.0 / (1 if group == "peaking" else assumptions.tranches)
            generators.append(
                Generator(
                    name=f"{group}_{k + 1}",
                    technology=group,
                    capacity_mw=(mw * assumptions.availability * share).rename(None),
                    marginal_cost=(fuel_cost / eta + assumptions.variable_cost).rename(None),
                    emissions_t_per_mwh=EMISSION_FACTORS[fuel_name] / eta,
                )
            )
    return generators


def build_system(
    mix: pd.DataFrame,
    inputs: SystemInputs,
    assumptions: FleetAssumptions | None = None,
    adjustments: Adjustments | None = None,
    storage: Sequence[Storage] = (),
    voll: float = DEFAULT_VOLL,
) -> SystemSpec:
    """GB on one bus for one calendar year of the generation mix (MW per period).

    Demand is NESO's total generation. Fixed profiles keep their (scaled) historic output;
    wind and solar can be curtailed; thermal plant follows the merit order.
    """
    adjustments = adjustments or Adjustments()
    if mix.isna().any().any():
        raise DataError("generation mix has missing values; use complete days")
    index = pd.DatetimeIndex(mix.index)
    zero = pd.Series(0.0, index=index)
    generators = [
        Generator(
            name=name,
            technology=name,
            capacity_mw=(mix[column] * adjustments.scale.get(name, 1.0)).rename(None),
            marginal_cost=zero,
            must_run=True,
        )
        for name, column in FIXED_PROFILES.items()
    ]
    for name, columns in RENEWABLE_PROFILES.items():
        output = mix[list(columns)].sum(axis=1) * adjustments.scale.get(name, 1.0)
        generators.append(Generator(name, name, output.rename(None), zero))
    generators += thermal_generators(index, inputs, assumptions, adjustments)
    return SystemSpec(mix["generation"].rename(None), tuple(generators), tuple(storage), voll)


def _efficiencies(
    group: str, fleet: dict[str, float], assumptions: FleetAssumptions
) -> list[float]:
    if group == "peaking":
        return [assumptions.peaking_efficiency]
    spread = assumptions.ccgt_spread if group == "ccgt" else assumptions.coal_spread
    offsets = (
        np.linspace(-spread, spread, assumptions.tranches) if assumptions.tranches > 1 else [0.0]
    )
    return [fleet[group] + float(offset) for offset in offsets]


def _check_keys(name: str, values: Mapping[str, float], allowed: Sequence[str]) -> None:
    unknown = sorted(set(values) - set(allowed))
    if unknown:
        raise ConfigError(
            f"{name}: unknown keys {', '.join(unknown)}; allowed: {', '.join(allowed)}"
        )
    for key, value in values.items():
        _check_non_negative(f"{name}.{key}", value)


def _check_non_negative(name: str, value: float) -> None:
    if not (math.isfinite(value) and value >= 0):
        raise ConfigError(f"{name} must be non-negative, got {value}")
