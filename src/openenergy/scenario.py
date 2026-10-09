"""YAML scenarios: load, validate, run and write results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import pydantic
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo

import openenergy
from openenergy.assets.battery import BatterySpec
from openenergy.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from openenergy.data.opsd import OPSD_ATTRIBUTION, OPSDCsvSource
from openenergy.data.series import fill_gaps
from openenergy.dispatch.arbitrage import DispatchConfig
from openenergy.errors import ConfigError
from openenergy.forecast.baseline import (
    Forecaster,
    NaiveLastWeek,
    NoisyForesight,
    PerfectForesight,
)
from openenergy.metrics.summary import Summary, summarise

ForecastMethod = Literal["perfect_foresight", "naive_last_week", "noisy_foresight"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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
        base = (info.context or {}).get("base")
        if base is not None and not value.is_absolute():
            value = Path(base) / value
        return value.resolve()


class ForecastSection(_Strict):
    method: ForecastMethod = "naive_last_week"
    error_std: float | None = Field(default=None, ge=0)
    seed: int = 0

    @pydantic.model_validator(mode="after")
    def _noise_needs_spread(self) -> ForecastSection:
        if self.method == "noisy_foresight" and self.error_std is None:
            raise ValueError("error_std is required for noisy_foresight")
        return self


class Scenario(_Strict):
    # Restricted so the name is safe to use as an output directory.
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    data: DataSection
    battery: BatterySpec
    forecast: ForecastSection = ForecastSection()
    dispatch: DispatchConfig = DispatchConfig()
    lead_hours: float = Field(default=12.0, ge=0)

    @pydantic.field_validator("forecast", mode="before")
    @classmethod
    def _method_shorthand(cls, value: Any) -> Any:
        return {"method": value} if isinstance(value, str) else value


@dataclass(frozen=True)
class ScenarioRun:
    scenario: Scenario
    result: BacktestResult
    benchmark: BacktestResult | None
    summary: Summary
    filled_intervals: int = 0
    attribution: str = field(default=OPSD_ATTRIBUTION)


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
    source = OPSDCsvSource(scenario.data.path)
    raw = source.prices(scenario.data.zone, scenario.data.start, scenario.data.end)
    prices, filled = fill_gaps(raw, scenario.data.max_gap_hours)
    config = BacktestConfig(lead_hours=scenario.lead_hours, dispatch=scenario.dispatch)

    forecaster = _forecaster(scenario.forecast, prices)
    result = run_backtest(scenario.battery, prices, forecaster, config)
    benchmark: BacktestResult | None = None
    if scenario.forecast.method == "perfect_foresight":
        summary = summarise(result, benchmark=result)
    else:
        benchmark = run_backtest(
            scenario.battery, prices, PerfectForesight(prices), config, days=result.daily.index
        )
        summary = summarise(result, benchmark=benchmark)
    return ScenarioRun(scenario, result, benchmark, summary, filled_intervals=filled)


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
    (out / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    return out


def _forecaster(section: ForecastSection, prices: Any) -> Forecaster:
    if section.method == "perfect_foresight":
        return PerfectForesight(prices)
    if section.method == "noisy_foresight":
        return NoisyForesight(prices, error_std=section.error_std or 0.0, seed=section.seed)
    return NaiveLastWeek()
