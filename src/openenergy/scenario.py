"""YAML scenarios: load, validate, run and write results."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import pydantic
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo

import openenergy
from openenergy.assets.battery import BatterySpec
from openenergy.assets.renewable import RenewableSpec
from openenergy.backtest.engine import (
    BacktestConfig,
    BacktestResult,
    Carbon,
    PlantResult,
    Site,
    run_backtest,
    run_plant_backtest,
)
from openenergy.data.carbon import CARBON_ATTRIBUTION, CarbonIntensitySource
from openenergy.data.opsd import OPSD_ATTRIBUTION, OPSDCsvSource
from openenergy.data.series import PriceSeries, fill_gaps
from openenergy.dispatch.arbitrage import DispatchConfig
from openenergy.dispatch.colocated import GridConnection
from openenergy.errors import ConfigError
from openenergy.forecast.baseline import (
    Forecaster,
    NaiveLastWeek,
    NoisyForesight,
    PerfectForesight,
)
from openenergy.metrics.capture import CaptureMetrics, capture_metrics
from openenergy.metrics.summary import Summary, summarise

ForecastMethod = Literal[
    "perfect_foresight", "naive_last_week", "noisy_foresight", "gradient_boosting"
]
# Prices loaded before data.start as forecaster history only; covers the 14-day lag.
WARMUP_DAYS = 14


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _resolve(value: Path, info: ValidationInfo) -> Path:
    """Resolve a path relative to the scenario file's directory."""
    base = (info.context or {}).get("base")
    if base is not None and not value.is_absolute():
        value = Path(base) / value
    return value.resolve()


class DataSection(_Strict):
    source: Literal["opsd"] = "opsd"
    path: Path
    zone: str = "GB_GBN"
    start: date | None = None
    end: date | None = None
    max_gap_hours: float = Field(default=2.0, ge=0)

    @pydantic.field_validator("path")
    @classmethod
    def _resolve_path(cls, value: Path, info: ValidationInfo) -> Path:
        return _resolve(value, info)


class ForecastSection(_Strict):
    method: ForecastMethod = "naive_last_week"
    error_std: float | None = Field(default=None, ge=0)
    seed: int = 0
    train_start: date | None = None
    train_end: date | None = None

    @pydantic.model_validator(mode="after")
    def _method_requirements(self) -> ForecastSection:
        if self.method == "noisy_foresight" and self.error_std is None:
            raise ValueError("error_std is required for noisy_foresight")
        if self.method == "gradient_boosting" and self.train_end is None:
            raise ValueError("train_end is required for gradient_boosting")
        if self.train_start and self.train_end and self.train_start > self.train_end:
            raise ValueError("train_start must not be after train_end")
        return self


class PlantSection(_Strict):
    capacity_mw: float = Field(gt=0)
    degradation_per_year: float = Field(default=0.0, ge=0, lt=1)
    technology: str | None = None


class AssetsSection(_Strict):
    """Renewable plants sharing the battery's grid connection."""

    pv: PlantSection | None = None
    wind: PlantSection | None = None

    @pydantic.model_validator(mode="after")
    def _at_least_one(self) -> AssetsSection:
        if self.pv is None and self.wind is None:
            raise ValueError("assets needs at least one of pv or wind")
        return self

    def plants(self) -> list[RenewableSpec]:
        defaults = {"pv": (self.pv, "solar"), "wind": (self.wind, "wind")}
        return [
            RenewableSpec(
                section.technology or tech, section.capacity_mw, section.degradation_per_year
            )
            for section, tech in defaults.values()
            if section is not None
        ]


class GridSection(_Strict):
    """Shared connection; export defaults to total plant capacity, import to export."""

    export_limit_mw: float | None = Field(default=None, ge=0)
    import_limit_mw: float | None = Field(default=None, ge=0)
    premium_per_mwh: float = 0.0


class CarbonSection(_Strict):
    """Carbon intensity file, an optional carbon price, and what dispatch plans on."""

    path: Path
    price_per_t: float = Field(default=0.0, ge=0)
    planning: Literal["last_week", "actual"] = "last_week"

    @pydantic.field_validator("path")
    @classmethod
    def _resolve_path(cls, value: Path, info: ValidationInfo) -> Path:
        return _resolve(value, info)


class Scenario(_Strict):
    # Restricted so the name is safe to use as an output directory.
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    data: DataSection
    battery: BatterySpec
    forecast: ForecastSection = ForecastSection()
    dispatch: DispatchConfig = DispatchConfig()
    lead_hours: float = Field(default=12.0, ge=0)
    assets: AssetsSection | None = None
    grid: GridSection | None = None
    carbon: CarbonSection | None = None

    @pydantic.field_validator("forecast", mode="before")
    @classmethod
    def _method_shorthand(cls, value: Any) -> Any:
        return {"method": value} if isinstance(value, str) else value

    @pydantic.model_validator(mode="after")
    def _grid_needs_assets(self) -> Scenario:
        if self.grid is not None and self.assets is None:
            raise ValueError("grid applies only to co-located assets; add an assets section")
        return self

    def connection(self) -> GridConnection | None:
        """The shared grid connection, or None for a battery-only scenario."""
        if self.assets is None:
            return None
        grid = self.grid or GridSection()
        capacity = sum(plant.capacity_mw for plant in self.assets.plants())
        export = capacity if grid.export_limit_mw is None else grid.export_limit_mw
        return GridConnection(export, grid.import_limit_mw, grid.premium_per_mwh)

    @pydantic.model_validator(mode="after")
    def _training_precedes_backtest(self) -> Scenario:
        train_end = self.forecast.train_end
        if train_end is None:
            return self
        if self.data.start is None:
            raise ValueError("data.start is required when the forecast has a training window")
        if train_end >= self.data.start:
            raise ValueError(
                f"forecast.train_end ({train_end}) must be before data.start ({self.data.start})"
            )
        return self


@dataclass(frozen=True)
class Colocation:
    """Site total against the same plant and battery on separate connections (common days)."""

    colocated: float
    plant_alone: float
    battery_alone: float

    @property
    def value(self) -> float:
        return self.colocated - self.plant_alone - self.battery_alone

    def to_dict(self) -> dict[str, float]:
        return {**dataclasses.asdict(self), "value": self.value}


@dataclass(frozen=True)
class ScenarioRun:
    scenario: Scenario
    result: BacktestResult
    benchmark: BacktestResult | None
    summary: Summary
    filled_intervals: int = 0
    attribution: str = field(default=OPSD_ATTRIBUTION)
    colocation: Colocation | None = None
    plant_capture: CaptureMetrics | None = None
    clipped_intervals: int = 0
    carbon_rejected: int | None = None


def load_scenario(path: str | Path) -> Scenario:
    """Read and validate a scenario; relative data paths resolve against the file."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"scenario file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: scenario must be a mapping of settings")
    try:
        return Scenario.model_validate(raw, context={"base": path.parent})
    except pydantic.ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ConfigError(f"{path}: {problems}") from exc
    except ConfigError as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def run_scenario(scenario: Scenario) -> ScenarioRun:
    """Backtest the scenario and, unless it is already perfect foresight, its benchmark."""
    data = scenario.data
    source = OPSDCsvSource(data.path)
    load_start = data.start - timedelta(days=WARMUP_DAYS) if data.start else None
    raw = source.prices(data.zone, load_start, data.end)
    prices, filled = fill_gaps(raw, data.max_gap_hours)
    config = BacktestConfig(lead_hours=scenario.lead_hours, dispatch=scenario.dispatch)
    days = None
    if data.start is not None:
        last = data.end or pd.DatetimeIndex(prices.prices.index)[-1].date()
        days = [data.start + timedelta(days=i) for i in range((last - data.start).days + 1)]

    forecaster = _forecaster(scenario, source, prices)
    site, clipped = _site(scenario, source, prices, load_start)
    carbon, rejected = _carbon(scenario, prices, load_start)
    result = run_backtest(
        scenario.battery, prices, forecaster, config, days=days, site=site, carbon=carbon
    )
    simulated = list(result.daily.index)
    benchmark: BacktestResult | None = None
    if scenario.forecast.method == "perfect_foresight":
        summary = summarise(result, benchmark=result)
    else:
        benchmark = run_backtest(
            scenario.battery, prices, PerfectForesight(prices), config, simulated, site, carbon
        )
        summary = summarise(result, benchmark=benchmark)

    colocation = plant_capture = None
    if site is not None and scenario.assets is not None:
        capacity = sum(plant.capacity_mw for plant in scenario.assets.plants())
        own = GridConnection(capacity, 0.0, site.grid.premium_per_mwh)
        plant = run_plant_backtest(
            Site(site.available_mw, own), prices, forecaster, config, simulated
        )
        battery = run_backtest(
            scenario.battery, prices, forecaster, config, simulated, carbon=carbon
        )
        colocation = _compare(result, plant, battery)
        output = site.available_mw[_in_days(site.available_mw, simulated)]
        plant_capture = capture_metrics(prices, output, capacity, label="plant")
    return ScenarioRun(
        scenario,
        result,
        benchmark,
        summary,
        filled_intervals=filled,
        colocation=colocation,
        plant_capture=plant_capture,
        clipped_intervals=clipped,
        carbon_rejected=rejected,
    )


def write_outputs(run: ScenarioRun, directory: str | Path) -> Path:
    """Write intervals.csv, daily.csv and summary.json; returns the directory."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    run.result.intervals.to_csv(out / "intervals.csv", index_label="timestamp")
    run.result.daily.to_csv(out / "daily.csv", index_label="date")
    payload = {
        "scenario": run.scenario.name,
        "openenergy_version": openenergy.__version__,
        "summary": run.summary.to_dict(),
        "skipped": {day.isoformat(): reason for day, reason in run.result.skipped.items()},
        "filled_intervals": run.filled_intervals,
        "config": run.scenario.model_dump(mode="json"),
        "attribution": run.attribution,
    }
    if run.colocation is not None and run.plant_capture is not None:
        payload["colocation"] = run.colocation.to_dict()
        payload["plant_capture"] = run.plant_capture.to_dict()
        payload["clipped_capacity_factors"] = run.clipped_intervals
        payload["note"] = (
            "Plans use actual plant output (perfect generation foresight), so co-location "
            "results are an upper bound."
        )
    if run.carbon_rejected is not None:
        payload["carbon_attribution"] = CARBON_ATTRIBUTION
        payload["carbon_rejected_values"] = run.carbon_rejected
        payload["carbon_note"] = (
            "Emissions use average grid carbon intensity; storage changes the marginal plant, "
            "whose emissions can differ. Negative emissions_t means net emissions avoided. "
            f"Dispatch planned on {run.scenario.carbon.planning if run.scenario.carbon else ''} "
            "intensity."
        )
    (out / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    return out


def _carbon(
    scenario: Scenario, prices: PriceSeries, start: date | None
) -> tuple[Carbon | None, int | None]:
    section = scenario.carbon
    if section is None:
        return None, None
    # Two weeks of extra history so last-week planning works from the first simulated day.
    history_start = start - timedelta(days=WARMUP_DAYS) if start else None
    loaded = CarbonIntensitySource(section.path).intensity(
        "actual", history_start, scenario.data.end, step=prices.step
    )
    actual, _ = fill_gaps(loaded, scenario.data.max_gap_hours)
    return Carbon(actual.values, section.price_per_t, section.planning), loaded.rejected


def _site(
    scenario: Scenario, source: OPSDCsvSource, prices: PriceSeries, start: date | None
) -> tuple[Site | None, int]:
    grid = scenario.connection()
    if grid is None or scenario.assets is None:
        return None, 0
    total = pd.Series(0.0, index=prices.prices.index)
    clipped = 0
    for plant in scenario.assets.plants():
        profile = source.profile(scenario.data.zone, plant.technology, start, scenario.data.end)
        clipped += profile.clipped
        profile, _ = fill_gaps(profile, scenario.data.max_gap_hours)
        total = total + plant.generation_mw(profile).reindex(total.index)
    return Site(total, grid), clipped


def _in_days(series: pd.Series[float], days: list[date]) -> Any:
    return pd.DatetimeIndex(series.index).normalize().isin(pd.to_datetime(days).tz_localize("UTC"))


def _compare(result: BacktestResult, plant: PlantResult, battery: BacktestResult) -> Colocation:
    common = result.daily.index.intersection(plant.daily.index).intersection(battery.daily.index)

    def total(daily: pd.DataFrame) -> float:
        rows = daily.loc[common]
        premium = float(rows["premium"].sum()) if "premium" in rows else 0.0
        return float(rows["revenue"].sum()) + premium

    return Colocation(total(result.daily), total(plant.daily), total(battery.daily))


def _forecaster(scenario: Scenario, source: OPSDCsvSource, prices: PriceSeries) -> Forecaster:
    section = scenario.forecast
    if section.method == "perfect_foresight":
        return PerfectForesight(prices)
    if section.method == "noisy_foresight":
        return NoisyForesight(prices, error_std=section.error_std or 0.0, seed=section.seed)
    if section.method == "gradient_boosting":
        try:
            from openenergy.forecast.ml import GradientBoostingForecaster
        except ImportError as exc:
            raise ConfigError(
                "gradient_boosting needs the forecast extra: pip install 'openenergy[forecast]'"
            ) from exc
        training = source.prices(scenario.data.zone, section.train_start, section.train_end)
        training, _ = fill_gaps(training, scenario.data.max_gap_hours)
        model = GradientBoostingForecaster(lead_hours=scenario.lead_hours, seed=section.seed)
        return model.fit(training.prices)
    return NaiveLastWeek()
