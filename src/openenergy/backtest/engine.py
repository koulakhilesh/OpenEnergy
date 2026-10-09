"""Rolling day-ahead backtest: plan on forecasts, settle at actual prices."""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import numpy.typing as npt
import pandas as pd

from openenergy.assets.battery import BatterySpec, BatteryState, age, apply_dispatch
from openenergy.data.series import PriceSeries
from openenergy.dispatch.arbitrage import DispatchConfig, optimise_dispatch
from openenergy.dispatch.colocated import (
    ColocatedPlan,
    GridConnection,
    dispatch_plant,
    optimise_colocated,
)
from openenergy.errors import ConfigError, DataError, InfeasibleDispatchError
from openenergy.forecast.baseline import Forecaster

FloatArray = npt.NDArray[np.float64]

INTERVAL_COLUMNS = ["price", "forecast", "charge_mw", "discharge_mw", "energy_mwh", "revenue"]
DAILY_COLUMNS = [
    "revenue",
    "expected_revenue",
    "charged_mwh",
    "discharged_mwh",
    "equivalent_cycles",
    "soh",
    "energy_mwh",
]
SITE_INTERVAL_COLUMNS = [
    "price",
    "forecast",
    "available_mw",
    "plant_to_grid_mw",
    "plant_to_battery_mw",
    "curtailed_mw",
    "grid_to_battery_mw",
    "charge_mw",
    "discharge_mw",
    "export_mw",
    "energy_mwh",
    "revenue",
    "premium",
]
SITE_DAILY_COLUMNS = [
    "revenue",
    "premium",
    "expected_revenue",
    "available_mwh",
    "curtailed_mwh",
    "charged_mwh",
    "discharged_mwh",
    "equivalent_cycles",
    "soh",
    "energy_mwh",
]
PLANT_DAILY_COLUMNS = ["revenue", "premium", "available_mwh", "curtailed_mwh"]


@dataclass(frozen=True)
class BacktestConfig:
    """``lead_hours``: how long before each UTC day the plan is fixed (12 = noon the day before)."""

    lead_hours: float = 12.0
    dispatch: DispatchConfig = field(default_factory=DispatchConfig)

    def __post_init__(self) -> None:
        if not (math.isfinite(self.lead_hours) and self.lead_hours >= 0):
            raise ConfigError(f"lead_hours must be non-negative, got {self.lead_hours}")


@dataclass(frozen=True, eq=False)
class Site:
    """Renewable output (MW, on the price grid) sharing ``grid`` with the battery.

    Output is known when planning (perfect generation foresight).
    """

    available_mw: pd.Series[float]
    grid: GridConnection


@dataclass(frozen=True)
class BacktestResult:
    """Interval and daily results; ``skipped`` maps unsimulated days to the reason."""

    spec: BatterySpec
    intervals: pd.DataFrame
    daily: pd.DataFrame
    skipped: dict[date, str]
    final_state: BatteryState
    forecaster: str
    currency: str
    step_hours: float
    site: Site | None = None


@dataclass(frozen=True)
class PlantResult:
    """A renewable plant operated on its own connection."""

    daily: pd.DataFrame
    skipped: dict[date, str]


def run_backtest(
    spec: BatterySpec,
    prices: PriceSeries,
    forecaster: Forecaster,
    config: BacktestConfig | None = None,
    days: Iterable[date] | None = None,
    site: Site | None = None,
) -> BacktestResult:
    """Simulate each UTC day in order; the battery ages through every calendar day in range.

    With a ``site``, the battery shares a grid connection with renewable output.
    """
    config = config or BacktestConfig()
    dt = prices.step_hours
    state = spec.initial_state()
    frames: list[pd.DataFrame] = []
    daily: dict[date, dict[str, float]] = {}
    skipped: dict[date, str] = {}
    available = None if site is None else _on_grid(site.available_mw, prices)

    for day, step in _days(prices, forecaster, config, days, available):
        row: dict[str, float] | None = None
        if isinstance(step, str):
            skipped[day] = step
        elif step is not None:
            day_prices, forecast = step
            if site is None or available is None:
                state, row = _battery_day(
                    spec, state, day, day_prices, forecast, dt, config, frames
                )
            else:
                output = np.asarray(available.loc[day_prices.index], dtype=np.float64)
                state, row = _site_day(
                    spec, state, site.grid, day, day_prices, forecast, output, dt, config, frames
                )
        state = age(spec, state, hours=24.0)
        if row is not None:
            daily[day] = {**row, "soh": state.soh}

    if not daily:
        raise DataError(f"no days to simulate for {forecaster.name}; skipped {len(skipped)}")
    columns = DAILY_COLUMNS if site is None else SITE_DAILY_COLUMNS
    return BacktestResult(
        spec=spec,
        intervals=pd.concat(frames),
        daily=pd.DataFrame.from_dict(daily, orient="index", columns=columns),
        skipped=skipped,
        final_state=state,
        forecaster=forecaster.name,
        currency=prices.currency,
        step_hours=dt,
        site=site,
    )


def run_plant_backtest(
    site: Site,
    prices: PriceSeries,
    forecaster: Forecaster,
    config: BacktestConfig | None = None,
    days: Iterable[date] | None = None,
) -> PlantResult:
    """The plant alone: curtail when forecast price plus premium is negative, settle at actual."""
    config = config or BacktestConfig()
    dt = prices.step_hours
    available = _on_grid(site.available_mw, prices)
    daily: dict[date, dict[str, float]] = {}
    skipped: dict[date, str] = {}
    for day, step in _days(prices, forecaster, config, days, available):
        if isinstance(step, str):
            skipped[day] = step
        elif step is not None:
            day_prices, forecast = step
            output = np.asarray(available.loc[day_prices.index], dtype=np.float64)
            plan = dispatch_plant(output, forecast, dt, site.grid)
            price = np.asarray(day_prices, dtype=np.float64)
            daily[day] = {
                "revenue": float(price @ plan.export_mw * dt),
                "premium": plan.expected_premium,
                "available_mwh": float(output.sum() * dt),
                "curtailed_mwh": float(plan.curtailed_mw.sum() * dt),
            }
    if not daily:
        raise DataError(f"no days to simulate for the plant; skipped {len(skipped)}")
    return PlantResult(
        daily=pd.DataFrame.from_dict(daily, orient="index", columns=PLANT_DAILY_COLUMNS),
        skipped=skipped,
    )


def _days(
    prices: PriceSeries,
    forecaster: Forecaster,
    config: BacktestConfig,
    days: Iterable[date] | None,
    available: pd.Series[float] | None,
) -> Iterator[tuple[date, str | tuple[pd.Series[float], FloatArray] | None]]:
    """Yield every calendar day in range with a skip reason, (prices, forecast), or None.

    None marks days outside the requested set; the battery still ages through them.
    """
    actual = prices.prices
    index = pd.DatetimeIndex(actual.index)
    complete = set(prices.complete_days())
    if available is not None:
        ppd = prices.periods_per_day
        counts = available.groupby(pd.DatetimeIndex(available.index).normalize()).count()
        complete &= {ts.date() for ts in counts.index[counts == ppd]}
    first, last = index[0].date(), index[-1].date()
    requested = _calendar(first, last) if days is None else sorted(set(days))
    if not requested:
        raise DataError("no days to simulate")
    wanted = set(requested)
    lead = pd.Timedelta(hours=config.lead_hours)

    for day in _calendar(requested[0], requested[-1]):
        if day not in wanted:
            yield day, None
        elif day not in complete:
            yield day, "incomplete or missing actual prices or plant output"
        else:
            day_prices = prices.day(day)
            start = pd.Timestamp(day, tz="UTC")
            history = actual.iloc[: index.searchsorted(start - lead)]
            try:
                forecast = forecaster.forecast(history, pd.DatetimeIndex(day_prices.index))
            except DataError as exc:
                yield day, str(exc)
            else:
                yield day, (day_prices, forecast)


def _on_grid(available: pd.Series[float], prices: PriceSeries) -> pd.Series[float]:
    if (available.dropna() < 0).any():
        raise DataError("plant output must be non-negative")
    return available.reindex(prices.prices.index)


def _battery_day(
    spec: BatterySpec,
    state: BatteryState,
    day: date,
    day_prices: pd.Series[float],
    forecast: FloatArray,
    dt: float,
    config: BacktestConfig,
    frames: list[pd.DataFrame],
) -> tuple[BatteryState, dict[str, float]]:
    try:
        plan = optimise_dispatch(spec, state, forecast, dt, config.dispatch)
    except InfeasibleDispatchError as exc:
        raise InfeasibleDispatchError(f"{day}: {exc}") from exc
    outcome = apply_dispatch(spec, state, plan.charge_mw, plan.discharge_mw, dt)
    price = np.asarray(day_prices, dtype=np.float64)
    revenue = price * (plan.discharge_mw - plan.charge_mw) * dt
    frames.append(
        pd.DataFrame(
            {
                "price": price,
                "forecast": forecast,
                "charge_mw": plan.charge_mw,
                "discharge_mw": plan.discharge_mw,
                "energy_mwh": outcome.energy_mwh[1:],
                "revenue": revenue,
            },
            index=day_prices.index,
        )
    )
    new = outcome.state
    row = {
        "revenue": float(revenue.sum()),
        "expected_revenue": plan.expected_revenue,
        "charged_mwh": float(plan.charge_mw.sum() * dt),
        "discharged_mwh": float(plan.discharge_mw.sum() * dt),
        "equivalent_cycles": new.equivalent_cycles,
        "energy_mwh": new.energy_mwh,
    }
    return new, row


def _site_day(
    spec: BatterySpec,
    state: BatteryState,
    grid: GridConnection,
    day: date,
    day_prices: pd.Series[float],
    forecast: FloatArray,
    available: FloatArray,
    dt: float,
    config: BacktestConfig,
    frames: list[pd.DataFrame],
) -> tuple[BatteryState, dict[str, float]]:
    try:
        plan: ColocatedPlan = optimise_colocated(
            spec, state, available, forecast, dt, grid, config.dispatch
        )
    except InfeasibleDispatchError as exc:
        raise InfeasibleDispatchError(f"{day}: {exc}") from exc
    outcome = apply_dispatch(spec, state, plan.charge_mw, plan.discharge_mw, dt)
    price = np.asarray(day_prices, dtype=np.float64)
    revenue = price * plan.export_mw * dt
    premium = grid.premium_per_mwh * (plan.plant_to_grid_mw + plan.plant_to_battery_mw) * dt
    frames.append(
        pd.DataFrame(
            {
                "price": price,
                "forecast": forecast,
                "available_mw": available,
                "plant_to_grid_mw": plan.plant_to_grid_mw,
                "plant_to_battery_mw": plan.plant_to_battery_mw,
                "curtailed_mw": plan.curtailed_mw,
                "grid_to_battery_mw": plan.grid_to_battery_mw,
                "charge_mw": plan.charge_mw,
                "discharge_mw": plan.discharge_mw,
                "export_mw": plan.export_mw,
                "energy_mwh": outcome.energy_mwh[1:],
                "revenue": revenue,
                "premium": premium,
            },
            index=day_prices.index,
        )
    )
    new = outcome.state
    row = {
        "revenue": float(revenue.sum()),
        "premium": float(premium.sum()),
        "expected_revenue": plan.expected_revenue,
        "available_mwh": float(available.sum() * dt),
        "curtailed_mwh": float(plan.curtailed_mw.sum() * dt),
        "charged_mwh": float(plan.charge_mw.sum() * dt),
        "discharged_mwh": float(plan.discharge_mw.sum() * dt),
        "equivalent_cycles": new.equivalent_cycles,
        "energy_mwh": new.energy_mwh,
    }
    return new, row


def _calendar(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]
