"""Forward scenarios: NESO FES pathways and interconnector links on a historic weather year."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from openenergy.data.fes import FesSource
from openenergy.data.interconnectors import NeighbourPriceSource, interconnectors
from openenergy.errors import ConfigError, DataError
from openenergy.system.model import Link, Storage

FES_YEARS = (2025, 2035)
# Irish day-ahead prices start in October 2018, so links need a weather year from 2019.
LINKS_FROM = 2019
# FES technology types behind each scalable historic profile.
PROFILE_TYPES = {
    "wind": ("Offshore Wind", "Onshore Wind"),
    "solar": ("Solar PV",),
    "nuclear": ("Nuclear",),
    "biomass": ("Biomass", "CCS Biomass"),
    "hydro": ("Hydro",),
}
# Hydrogen and CCS gas have no open cost data; they are counted as gas plant.
GAS_TYPES = ("Gas", "CCS Gas", "Hydrogen")
LDES = "Long Duration Energy Storage"
FES_NOTE = (
    "FES scenario: capacities and annual demand scaled from NESO's Future Energy Scenarios "
    "relative to the weather year, which keeps its weather, demand shape and fuel and "
    "carbon prices; hydrogen and CCS gas are counted as gas plant; FES batteries and new "
    "long-duration storage are added as storage fleets."
)
LINKS_NOTE = (
    "Interconnectors are price-taking links: each imports when GB's price is above the "
    "neighbour's actual day-ahead price in the weather year and exports when below, up to "
    "its capacity; on 2024 this imports about half as much again as actually flowed."
)


@dataclass(frozen=True)
class FesChanges:
    """What a FES pathway and year change on the weather year's system."""

    scale: dict[str, float]
    capacity_mw: dict[str, float]
    storage: tuple[Storage, ...]
    link_scale: float


def fes_changes(
    source: FesSource,
    pathway: str,
    year: int,
    base_year: int,
    thermal_mw: Mapping[str, float],
    battery_efficiency: float,
    ldes_efficiency: float,
) -> FesChanges:
    """Ratios of FES ``year`` to FES ``base_year`` applied to the weather year's system.

    ``thermal_mw`` is the weather year's installed CCGT and peaking capacity (DUKES); both
    scale with FES gas. Coal is zero (FES has none). FES batteries are added in full, and
    long-duration storage beyond the base year's (pumped storage keeps its historic output).
    """
    if not FES_YEARS[0] <= year <= FES_YEARS[1]:
        raise ConfigError(f"FES year must be {FES_YEARS[0]} to {FES_YEARS[1]}, got {year}")
    if year < base_year:
        raise ConfigError(f"FES year {year} is before the weather year {base_year}")
    target = source.capacity_mw(pathway, year)
    base = source.capacity_mw(pathway, base_year)
    scale = {name: _ratio(target, base, types) for name, types in PROFILE_TYPES.items()}
    scale["demand"] = source.demand_gwh(pathway, year) / source.demand_gwh(pathway, base_year)
    gas = _ratio(target, base, GAS_TYPES)
    capacity = {group: mw * gas for group, mw in thermal_mw.items()}
    capacity["coal"] = 0.0

    energy, base_energy = source.storage_gwh(pathway, year), source.storage_gwh(pathway, base_year)
    storage = []
    battery_mw = float(target.get("Battery", 0.0))
    if battery_mw > 0:
        hours = float(energy.get("Battery", 0.0)) * 1000 / battery_mw
        storage.append(Storage("fes_battery", battery_mw, hours, battery_efficiency))
    extra_mw = float(target.get(LDES, 0.0) - base.get(LDES, 0.0))
    extra_mwh = float(energy.get(LDES, 0.0) - base_energy.get(LDES, 0.0)) * 1000
    if extra_mw > 0 and extra_mwh > 0:
        storage.append(
            Storage("fes_long_duration", extra_mw, extra_mwh / extra_mw, ldes_efficiency)
        )
    return FesChanges(scale, capacity, tuple(storage), _ratio(target, base, ("Interconnectors",)))


def links(
    index: pd.DatetimeIndex,
    system_dir: str | Path,
    prices_path: str | Path,
    scale: float = 1.0,
    hurdle: float = 0.0,
    availability: float = 1.0,
) -> tuple[Link, ...]:
    """One price-taking link per GB interconnector in service on each snapshot."""
    source = NeighbourPriceSource(prices_path)
    built = []
    for unit in interconnectors(system_dir):
        live = (
            pd.Series(1.0, index=index)
            if unit.in_service is None
            else pd.Series((index >= unit.in_service).astype(float), index=index)
        )
        if not live.any():
            continue
        factor = live * scale * availability
        try:
            price = source.prices(unit.neighbour, index).prices
        except DataError as exc:
            raise DataError(f"{unit.name}: {exc}") from exc
        built.append(
            Link(
                unit.name,
                (factor * unit.import_mw).rename(None),
                (factor * unit.export_mw).rename(None),
                price.rename(None),
                hurdle,
            )
        )
    return tuple(built)


def price_column(pathway: str, year: int) -> str:
    """Column name for a pathway and year in ``data/scenarios/fes_prices.csv``."""
    return f"{pathway.lower().replace(' ', '_')}_{year}"


def _ratio(target: pd.Series[float], base: pd.Series[float], types: tuple[str, ...]) -> float:
    now = float(sum(base.get(t, 0.0) for t in types))
    later = float(sum(target.get(t, 0.0) for t in types))
    if now <= 0:
        if later > 0:
            raise DataError(f"FES has no {', '.join(types)} in the weather year to scale from")
        return 0.0
    return later / now
