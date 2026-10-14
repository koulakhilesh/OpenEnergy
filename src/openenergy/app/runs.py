"""What the app runs: one battery request, checked and run on historic or pathway prices."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path
from typing import Literal

import pandas as pd

from openenergy.assets.battery import BatterySpec
from openenergy.backtest.engine import BacktestConfig, run_backtest
from openenergy.data.fes import FES_ATTRIBUTION, PATHWAYS
from openenergy.data.fleet import FLEET_ATTRIBUTION
from openenergy.data.interconnectors import INTERCONNECTOR_ATTRIBUTION
from openenergy.data.neso import MIX_ATTRIBUTION
from openenergy.data.series import PriceSeries
from openenergy.dispatch.arbitrage import DispatchConfig
from openenergy.errors import DataError
from openenergy.forecast.baseline import Forecaster, NaiveLastWeek, PerfectForesight
from openenergy.metrics.summary import summarise
from openenergy.report.load import BatteryOutput, load_output
from openenergy.scenario import Scenario, run_scenario, write_outputs
from openenergy.system.forward import FES_NOTE, LINKS_NOTE, price_column
from openenergy.system.scenario import SYSTEM_NOTE

HISTORY_YEARS = (2017, 2025)
RESPONSE_FROM = 2022
SCENARIO_YEARS = (2030, 2035)
WEATHER_YEAR = 2025
SERVICES = {"none": [], "dc": ["DCL", "DCH"], "dc_dm": ["DCL", "DCH", "DML", "DMH"]}
DEGRADATION_COST = 5.0
SCENARIO_NOTE = (
    f"Prices are OpenEnergy's model of GB with this pathway's fleet and demand on "
    f"{WEATHER_YEAR}'s weather and fuel, carbon and neighbouring prices, not a forecast. "
    f"{SYSTEM_NOTE} {FES_NOTE} {LINKS_NOTE}"
)

Source = Literal["history", "scenario"]
ForecastName = Literal["naive_last_week", "perfect_foresight"]
Services = Literal["none", "dc", "dc_dm"]


@dataclass(frozen=True)
class Request:
    """A battery of ``hours`` duration valued per MW (revenue scales with power).

    ``year`` is the historic year for ``history`` and the FES year for ``scenario``.
    """

    source: Source
    year: int
    hours: float
    forecast: ForecastName = "naive_last_week"
    services: Services = "none"
    pathway: str | None = None

    @property
    def key(self) -> str:
        where = (
            f"gb-{self.year}"
            if self.source == "history"
            else price_column(str(self.pathway), self.year)
        )
        return f"{where}-{self.hours:g}h-{self.forecast}-{self.services}"

    @property
    def label(self) -> str:
        where = f"GB {self.year}" if self.source == "history" else f"{self.pathway} {self.year}"
        return f"{self.hours:g} h battery, {where}"

    def problem(self) -> str | None:
        """A fixed message if the request cannot run, so no exception text reaches a page."""
        if self.source == "scenario":
            if self.pathway not in PATHWAYS or self.year not in SCENARIO_YEARS:
                return f"Choose a FES pathway and {' or '.join(map(str, SCENARIO_YEARS))}."
            if self.services != "none":
                return "Frequency response is available on historic years only."
        else:
            if not HISTORY_YEARS[0] <= self.year <= HISTORY_YEARS[1]:
                return f"Choose a year from {HISTORY_YEARS[0]} to {HISTORY_YEARS[1]}."
            if self.services != "none" and self.year < RESPONSE_FROM:
                return f"Frequency response needs a year from {RESPONSE_FROM}."
        return None


def run(request: Request, data: Path, power_mw: float = 1.0) -> BatteryOutput:
    """Backtest the request and its perfect-foresight benchmark on the bundled data."""
    spec = BatterySpec(power_mw=power_mw, energy_mwh=power_mw * request.hours)
    data = data.resolve()
    if request.source == "history":
        return _history(spec, request, data)
    return _scenario(spec, request, data)


def _history(spec: BatterySpec, request: Request, data: Path) -> BatteryOutput:
    raw: dict[str, object] = {
        "name": f"gb-{request.year}",
        "data": {
            "source": "ember",
            "path": str(data / "prices/gb_day_ahead_ember.csv"),
            "start": date(request.year, 1, 1),
            "end": date(request.year, 12, 31),
        },
        "battery": {"power_mw": spec.power_mw, "energy_mwh": spec.energy_mwh},
        "forecast": request.forecast,
        "dispatch": {"degradation_cost": DEGRADATION_COST},
    }
    if request.services != "none":
        raw["response"] = {
            "path": str(data / "response/gb_dynamic_response.csv"),
            "services": SERVICES[request.services],
        }
    scenario = Scenario.model_validate(raw, context={"base": data})
    with tempfile.TemporaryDirectory() as tmp:
        output = load_output(write_outputs(run_scenario(scenario), Path(tmp) / "run"))
    if not isinstance(output, BatteryOutput):
        raise DataError("unexpected output")
    return output


def _scenario(spec: BatterySpec, request: Request, data: Path) -> BatteryOutput:
    column = price_column(str(request.pathway), request.year)
    prices = PriceSeries(fes_prices(data)[column].rename(None), currency="GBP", zone="GB_GBN")
    config = BacktestConfig(dispatch=DispatchConfig(degradation_cost=DEGRADATION_COST))
    perfect = PerfectForesight(prices)
    forecaster: Forecaster = perfect if request.forecast == "perfect_foresight" else NaiveLastWeek()
    result = run_backtest(spec, prices, forecaster, config)
    benchmark = (
        result
        if forecaster is perfect
        else run_backtest(spec, prices, perfect, config, list(result.daily.index))
    )
    attribution = " ".join(
        (MIX_ATTRIBUTION, FLEET_ATTRIBUTION, INTERCONNECTOR_ATTRIBUTION, FES_ATTRIBUTION)
    )
    return BatteryOutput(
        name=column,
        summary={
            "summary": summarise(result, benchmark=benchmark).to_dict(),
            "note": SCENARIO_NOTE,
            "attribution": attribution,
        },
        daily=result.daily,
        intervals=result.intervals,
        benchmark_daily=None if benchmark is result else benchmark.daily,
    )


@cache
def fes_prices(data: Path) -> pd.DataFrame:
    path = data / "scenarios/fes_prices.csv"
    if not path.is_file():
        raise DataError(f"precomputed scenario prices not found: {path.name}")
    frame = pd.read_csv(path, index_col="utc_timestamp")
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, format="ISO8601"))
    return frame
