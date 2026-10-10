"""Backcast: rebuild history with the system model and measure how far it is from reality."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from openenergy.data.fleet import EMISSION_FACTORS, FLEET_ATTRIBUTION, SystemInputs
from openenergy.data.neso import MIX_ATTRIBUTION
from openenergy.data.opsd import OPSD_ATTRIBUTION
from openenergy.data.series import PriceSeries
from openenergy.errors import DataError
from openenergy.system.fleet import Adjustments, FleetAssumptions, build_system
from openenergy.system.model import Backend, Storage, SystemResult, solve

# Carbon price support rates per fuel are published from 1 April 2015; OPSD prices end
# 30 September 2020.
BACKCAST_START = date(2015, 4, 1)
BACKCAST_END = date(2020, 9, 30)
BACKCAST_NOTE = (
    "Cost-based model: plants bid short-run marginal cost (fuel, carbon price support, "
    "EU ETS). Imports, nuclear, biomass, hydro and pumped storage are fixed at historic "
    "output; demand is NESO total generation. No parameter is fitted to prices; scarcity "
    "pricing, start-up costs and bidding above cost are not modelled."
)
_MWH_PER_TWH = 1e6


@dataclass(frozen=True)
class BackcastYear:
    """Model vs reality for one year. Prices in GBP/MWh, energy in TWh, emissions in MtCO2.

    ``emissions_mt_actual_mix`` applies the model's emission factors and fleet-average
    efficiencies to the gas and coal that actually ran, so the two emission figures differ
    only because of dispatch.
    """

    year: int
    hours: int
    price_model: float
    price_actual: float
    bias: float
    mae: float
    correlation: float
    p95_model: float
    p95_actual: float
    gas_twh_model: float
    gas_twh_actual: float
    coal_twh_model: float
    coal_twh_actual: float
    emissions_mt_model: float
    emissions_mt_actual_mix: float
    unserved_mwh: float

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True, eq=False)
class Backcast:
    years: list[BackcastYear]
    hourly: pd.DataFrame = field(repr=False)
    results: dict[int, SystemResult] = field(repr=False)


def backcast(
    mix: pd.DataFrame,
    inputs: SystemInputs,
    prices: PriceSeries,
    assumptions: FleetAssumptions | None = None,
    adjustments: Adjustments | None = None,
    storage: Sequence[Storage] = (),
    backend: Backend = "auto",
) -> Backcast:
    """Solve each calendar year of ``mix`` and compare with actual prices and fuel use.

    Nothing is fitted: assumptions are applied as given and the gap is the finding.
    """
    index = pd.DatetimeIndex(mix.index)
    if len(index) < 2:
        raise DataError("generation mix needs at least two periods")
    if index[1] - index[0] != prices.step:
        raise DataError(f"mix step {index[1] - index[0]} differs from price step {prices.step}")
    years, frames, results = [], [], {}
    for year in sorted(set(index.year)):
        part = mix[index.year == year]
        result = solve(build_system(part, inputs, assumptions, adjustments, storage), backend)
        results[int(year)] = result
        frame = _hourly(part, result, prices)
        frames.append(frame)
        years.append(_compare(int(year), part, frame, result, inputs, prices.step))
    return Backcast(years, pd.concat(frames), results)


def _hourly(part: pd.DataFrame, result: SystemResult, prices: PriceSeries) -> pd.DataFrame:
    by_tech = result.by_technology()
    return pd.DataFrame(
        {
            "price_model": result.price,
            "price_actual": prices.prices.reindex(part.index),
            "gas_model_mw": by_tech["ccgt"] + by_tech["peaking"],
            "gas_actual_mw": part["gas"],
            "coal_model_mw": by_tech["coal"],
            "coal_actual_mw": part["coal"],
            "unserved_mw": result.unserved,
        }
    )


def _compare(
    year: int,
    part: pd.DataFrame,
    frame: pd.DataFrame,
    result: SystemResult,
    inputs: SystemInputs,
    step: pd.Timedelta,
) -> BackcastYear:
    hours = float(step / pd.Timedelta(hours=1))
    both = frame[["price_model", "price_actual"]].dropna()
    if len(both) < 2:
        raise DataError(f"no actual prices to compare in {year}")
    model, actual = both["price_model"], both["price_actual"]
    error = model - actual
    efficiency = inputs.efficiency(year)
    actual_emissions = (
        part["gas"].sum() * EMISSION_FACTORS["gas"] / efficiency["ccgt"]
        + part["coal"].sum() * EMISSION_FACTORS["coal"] / efficiency["coal"]
    ) * hours

    def twh(column: str) -> float:
        return float(frame[column].sum() * hours / _MWH_PER_TWH)

    return BackcastYear(
        year=year,
        hours=len(both),
        price_model=float(model.mean()),
        price_actual=float(actual.mean()),
        bias=float(error.mean()),
        mae=float(error.abs().mean()),
        correlation=float(np.corrcoef(model, actual)[0, 1]),
        p95_model=float(model.quantile(0.95)),
        p95_actual=float(actual.quantile(0.95)),
        gas_twh_model=twh("gas_model_mw"),
        gas_twh_actual=twh("gas_actual_mw"),
        coal_twh_model=twh("coal_model_mw"),
        coal_twh_actual=twh("coal_actual_mw"),
        emissions_mt_model=float(result.emissions_t.sum() / 1e6),
        emissions_mt_actual_mix=float(actual_emissions / 1e6),
        unserved_mwh=float(result.unserved.sum() * hours),
    )


def write_backcast(
    result: Backcast, directory: Path, assumptions: FleetAssumptions | None = None
) -> Path:
    """Write ``backcast.csv`` (per year), ``hourly.csv`` and ``summary.json`` with sources."""
    directory.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([y.to_dict() for y in result.years]).to_csv(
        directory / "backcast.csv", index=False
    )
    result.hourly.to_csv(directory / "hourly.csv", index_label="utc_timestamp")
    summary = {
        "years": [y.to_dict() for y in result.years],
        "assumptions": dataclasses.asdict(assumptions or FleetAssumptions()),
        "note": BACKCAST_NOTE,
        "attribution": [MIX_ATTRIBUTION, FLEET_ATTRIBUTION, OPSD_ATTRIBUTION],
    }
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return directory
