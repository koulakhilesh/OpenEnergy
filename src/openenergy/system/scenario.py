"""System scenarios: one GB year with changes, and optionally a battery valued on its prices."""

from __future__ import annotations

import dataclasses
import itertools
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import pydantic
from pydantic import AliasChoices, Field, ValidationInfo

import openenergy
from openenergy.assets.battery import BatterySpec
from openenergy.backtest.engine import BacktestConfig, run_backtest
from openenergy.data.ember import gb_prices
from openenergy.data.fleet import FLEET_ATTRIBUTION, UNIT_ATTRIBUTION, SystemInputs
from openenergy.data.neso import MIX_ATTRIBUTION, GenerationMixSource
from openenergy.data.series import PriceSeries
from openenergy.dispatch.arbitrage import DispatchConfig
from openenergy.errors import ConfigError
from openenergy.forecast.baseline import Forecaster, NaiveLastWeek, PerfectForesight
from openenergy.metrics.summary import Summary, summarise
from openenergy.scenario import MAX_SWEEP, _read, _resolve, _Strict, apply_overrides
from openenergy.system.commitment import Commitment
from openenergy.system.fleet import Adjustments, FleetAssumptions, build_system
from openenergy.system.model import PriceKind, Storage, SystemResult, solve
from openenergy.system.validate import (
    BACKCAST_START,
    COMMITMENT_NOTE,
    DATA_END,
    _daily_spread,
)

SYSTEM_NOTE = (
    "Cost-based dispatch of GB on one bus: plants bid short-run marginal cost; imports, "
    "nuclear, biomass, hydro and pumped storage follow (scaled) historic output; storage "
    "is optimised with perfect foresight over the year, so results are an idealised "
    "benchmark. Scarcity pricing is not modelled, and start-up costs only with unit "
    "commitment, so price spreads are narrower than in the real market."
)
_HOUR = pd.Timedelta(hours=1)


class StorageSection(_Strict):
    """Storage added to the system; ``power_mw: 0`` leaves it out (handy in sweeps)."""

    power_mw: float = Field(ge=0)
    hours: float = Field(gt=0)
    efficiency: float = Field(default=0.85, gt=0, le=1)


class AssumptionsSection(_Strict):
    tranches: int = Field(default=5, ge=1)
    availability: float = Field(default=0.9, gt=0, le=1)
    ccgt_spread: float = Field(default=0.04, ge=0, lt=0.2)
    coal_spread: float = Field(default=0.02, ge=0, lt=0.2)
    peaking_efficiency: float = Field(default=0.35, gt=0, le=1)
    variable_cost: float = Field(default=0.0, ge=0)


class SystemSection(_Strict):
    data: Path
    prices: list[Path] | None = None
    year: int = Field(ge=BACKCAST_START.year, le=DATA_END.year)
    start: date | None = None
    end: date | None = None
    scale: dict[str, float] = Field(default_factory=dict)
    capacity_mw: dict[str, float] = Field(default_factory=dict)
    fuel_price_scale: dict[str, float] = Field(default_factory=dict)
    # eu_ets_gbp_per_t is the v3.1 name, kept so older scenarios still load.
    ets_gbp_per_t: float | None = Field(
        default=None, ge=0, validation_alias=AliasChoices("ets_gbp_per_t", "eu_ets_gbp_per_t")
    )
    carbon_price_support: bool = True
    storage: dict[str, StorageSection] = Field(default_factory=dict)
    assumptions: AssumptionsSection = AssumptionsSection()
    voll: float = Field(default=6000.0, gt=0)
    backend: Literal["auto", "merit", "pypsa"] = "auto"
    commitment: bool = False
    lookahead_hours: float = Field(default=24.0, ge=0)
    price: Literal["marginal", "start"] = "marginal"

    @pydantic.model_validator(mode="after")
    def _start_price_needs_commitment(self) -> SystemSection:
        if self.price == "start" and not self.commitment:
            raise ValueError("price: start needs commitment: true")
        if self.commitment and self.backend != "auto":
            raise ValueError("commitment has its own solver; leave backend as auto")
        first, last = self.window()
        if first > last:
            raise ValueError(f"no days between {first} and {last} in {self.year}")
        return self

    @pydantic.field_validator("prices", mode="before")
    @classmethod
    def _one_or_many(cls, value: Any) -> Any:
        return [value] if isinstance(value, str | Path) else value

    @pydantic.field_validator("data")
    @classmethod
    def _resolve_path(cls, value: Path, info: ValidationInfo) -> Path:
        return _resolve(value, info)

    @pydantic.field_validator("prices")
    @classmethod
    def _resolve_paths(cls, value: list[Path] | None, info: ValidationInfo) -> list[Path] | None:
        return None if value is None else [_resolve(path, info) for path in value]

    def window(self) -> tuple[date, date]:
        """Days modelled: the year, narrowed by ``start``/``end`` and the data window."""
        first = max(date(self.year, 1, 1), BACKCAST_START, self.start or BACKCAST_START)
        last = min(date(self.year, 12, 31), DATA_END, self.end or DATA_END)
        return first, last


class SystemScenario(_Strict):
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    system: SystemSection
    battery: BatterySpec | None = None
    forecast: Literal["naive_last_week", "perfect_foresight"] = "naive_last_week"
    lead_hours: float = Field(default=12.0, ge=0)
    dispatch: DispatchConfig = DispatchConfig()


@dataclass(frozen=True)
class SystemSummary:
    """One scenario year. Prices GBP/MWh, energy TWh, emissions MtCO2, cost GBP million."""

    year: int
    periods: int
    price: str
    price_mean: float
    price_std: float
    price_p05: float
    price_p95: float
    daily_spread: float
    generation_twh: dict[str, float]
    curtailment_twh: float
    unserved_mwh: float
    emissions_mt: float
    cost_m: float
    storage_cycles: dict[str, float]
    actual_price_mean: float | None
    backend: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class SystemRun:
    scenario: SystemScenario
    result: SystemResult
    summary: SystemSummary
    battery: Summary | None
    battery_benchmark: Summary | None = None


def is_system_scenario(path: str | Path) -> bool:
    return "system" in _read(Path(path))


def load_system_scenario(path: str | Path) -> SystemScenario:
    path = Path(path)
    return _validate(_read(path), path)


def run_system_scenario(scenario: SystemScenario) -> SystemRun:
    """Solve the scenario year and, if a battery is given, backtest it on the modelled prices.

    The battery plans on forecasts from modelled history only, exactly as on market prices.
    """
    section = scenario.system
    first, last = section.window()
    mix = GenerationMixSource(section.data / "generation_mix.csv").mix(first, last, step=_HOUR)
    inputs = SystemInputs(section.data)
    spec = build_system(
        mix,
        inputs,
        FleetAssumptions(**section.assumptions.model_dump()),
        Adjustments(
            scale=section.scale,
            capacity_mw=section.capacity_mw,
            fuel_price_scale=section.fuel_price_scale,
            ets_gbp_per_t=section.ets_gbp_per_t,
            carbon_price_support=section.carbon_price_support,
        ),
        [
            Storage(name, unit.power_mw, unit.hours, unit.efficiency)
            for name, unit in section.storage.items()
            if unit.power_mw > 0
        ],
        section.voll,
    )
    commitment = (
        Commitment.from_inputs(inputs, section.lookahead_hours) if section.commitment else None
    )
    result = solve(spec, section.backend, commitment)
    actual = None
    if section.prices:
        actual = gb_prices(section.prices, first, last)[0].prices.mean()
    summary = _summarise(section.year, spec.storage, result, actual, section.price)
    if scenario.battery is None:
        return SystemRun(scenario, result, summary, None)
    prices = PriceSeries(result.price_of(section.price), currency="GBP", zone="GB_GBN")
    config = BacktestConfig(lead_hours=scenario.lead_hours, dispatch=scenario.dispatch)
    forecaster: Forecaster = (
        PerfectForesight(prices) if scenario.forecast == "perfect_foresight" else NaiveLastWeek()
    )
    run = run_backtest(scenario.battery, prices, forecaster, config)
    days = list(run.daily.index)
    benchmark = run_backtest(scenario.battery, prices, PerfectForesight(prices), config, days)
    return SystemRun(
        scenario,
        result,
        summary,
        summarise(run, benchmark=benchmark),
        summarise(benchmark, benchmark=benchmark),
    )


def write_system_outputs(run: SystemRun, directory: str | Path) -> Path:
    """Write ``dispatch.csv`` (hourly price and output by technology) and ``summary.json``."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    frame = run.result.by_technology()
    frame.insert(0, "price", run.result.price)
    if run.result.start_price is not None:
        frame.insert(1, "start_price", run.result.start_price)
    frame["curtailment"] = run.result.curtailment
    frame["emissions_t"] = run.result.emissions_t
    frame.to_csv(out / "dispatch.csv", index_label="utc_timestamp")
    attribution = [MIX_ATTRIBUTION, FLEET_ATTRIBUTION]
    if run.scenario.system.commitment:
        attribution.append(UNIT_ATTRIBUTION)
    if run.scenario.system.prices:
        first, last = run.scenario.system.window()
        attribution.extend(gb_prices(run.scenario.system.prices, first, last)[1])
    note = SYSTEM_NOTE + (" " + COMMITMENT_NOTE if run.scenario.system.commitment else "")
    payload: dict[str, Any] = {
        "scenario": run.scenario.name,
        "openenergy_version": openenergy.__version__,
        "system": run.summary.to_dict(),
        "config": run.scenario.model_dump(mode="json"),
        "note": note,
        "attribution": attribution,
    }
    if run.battery is not None and run.battery_benchmark is not None:
        payload["battery"] = run.battery.to_dict()
        payload["battery_perfect_foresight"] = run.battery_benchmark.to_dict()
    (out / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    return out


def system_sweep(path: str | Path, grid: dict[str, list[Any]]) -> pd.DataFrame:
    """Run a system scenario for every combination of ``grid`` values, in grid order."""
    path = Path(path)
    combinations = math.prod(len(values) for values in grid.values())
    if combinations > MAX_SWEEP:
        raise ConfigError(f"{combinations} combinations exceed the limit of {MAX_SWEEP}")
    raw = _read(path)
    rows = []
    for values in itertools.product(*grid.values()):
        overrides = dict(zip(grid, values, strict=True))
        run = run_system_scenario(_validate(apply_overrides(raw, overrides), path))
        s = run.summary
        row: dict[str, Any] = {
            **overrides,
            "price_mean": s.price_mean,
            "price_std": s.price_std,
            "daily_spread": s.daily_spread,
            "emissions_mt": s.emissions_mt,
            "curtailment_twh": s.curtailment_twh,
            "unserved_mwh": s.unserved_mwh,
            "cost_m": s.cost_m,
        }
        if run.battery is not None and run.battery_benchmark is not None:
            row["battery_per_mw_year"] = run.battery.revenue_per_mw_year
            row["battery_pf_per_mw_year"] = run.battery_benchmark.revenue_per_mw_year
        rows.append(row)
    return pd.DataFrame(rows)


def _validate(raw: dict[str, Any], path: Path) -> SystemScenario:
    try:
        return SystemScenario.model_validate(raw, context={"base": path.parent})
    except pydantic.ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ConfigError(f"{path}: {problems}") from exc
    except ConfigError as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def _summarise(
    year: int,
    storage: tuple[Storage, ...],
    result: SystemResult,
    actual: float | None,
    kind: PriceKind,
) -> SystemSummary:
    price = result.price_of(kind)
    hours = float(pd.Timedelta(price.index[1] - price.index[0]) / _HOUR)
    by_tech = result.by_technology()
    generation = {
        name: float(by_tech[name].sum() * hours / 1e6)
        for name in by_tech.columns
        if name not in ("unserved", "storage")
    }
    cycles = {
        unit.name: float(result.storage[unit.name].clip(lower=0).sum() * hours)
        / (unit.power_mw * unit.hours)
        for unit in storage
    }
    return SystemSummary(
        year=year,
        periods=len(price),
        price=kind,
        price_mean=float(price.mean()),
        price_std=float(price.std()),
        price_p05=float(price.quantile(0.05)),
        price_p95=float(price.quantile(0.95)),
        daily_spread=_daily_spread(price),
        generation_twh=generation,
        curtailment_twh=float(result.curtailment.sum() * hours / 1e6),
        unserved_mwh=float(result.unserved.sum() * hours),
        emissions_mt=float(result.emissions_t.sum() / 1e6),
        cost_m=result.cost / 1e6,
        storage_cycles=cycles,
        actual_price_mean=None if actual is None else float(actual),
        backend=result.backend,
    )
