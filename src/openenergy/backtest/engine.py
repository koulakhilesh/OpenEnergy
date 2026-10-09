"""Rolling day-ahead backtest: plan on forecasts, settle at actual prices."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from openenergy.assets.battery import BatterySpec, BatteryState, age, apply_dispatch
from openenergy.data.series import PriceSeries
from openenergy.dispatch.arbitrage import DispatchConfig, optimise_dispatch
from openenergy.errors import ConfigError, DataError, InfeasibleDispatchError
from openenergy.forecast.baseline import Forecaster

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


@dataclass(frozen=True)
class BacktestConfig:
    """``lead_hours``: how long before each UTC day the plan is fixed (12 = noon the day before)."""

    lead_hours: float = 12.0
    dispatch: DispatchConfig = field(default_factory=DispatchConfig)

    def __post_init__(self) -> None:
        if not (math.isfinite(self.lead_hours) and self.lead_hours >= 0):
            raise ConfigError(f"lead_hours must be non-negative, got {self.lead_hours}")


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


def run_backtest(
    spec: BatterySpec,
    prices: PriceSeries,
    forecaster: Forecaster,
    config: BacktestConfig | None = None,
    days: Iterable[date] | None = None,
) -> BacktestResult:
    """Simulate each UTC day in order; the battery ages through every calendar day in range."""
    config = config or BacktestConfig()
    actual = prices.prices
    complete = set(prices.complete_days())
    index = pd.DatetimeIndex(actual.index)
    first, last = index[0].date(), index[-1].date()
    requested = _calendar(first, last) if days is None else sorted(set(days))
    if not requested:
        raise DataError("no days to simulate")

    lead = pd.Timedelta(hours=config.lead_hours)
    dt = prices.step_hours
    state = spec.initial_state()
    wanted = set(requested)
    frames: list[pd.DataFrame] = []
    daily: dict[date, dict[str, float]] = {}
    skipped: dict[date, str] = {}

    for day in _calendar(requested[0], requested[-1]):
        row: dict[str, float] | None = None
        if day in wanted:
            if day not in complete:
                skipped[day] = "incomplete or missing actual prices"
            else:
                start = pd.Timestamp(day, tz="UTC")
                day_prices = prices.day(day)
                history = actual.iloc[: index.searchsorted(start - lead)]
                try:
                    forecast = forecaster.forecast(history, pd.DatetimeIndex(day_prices.index))
                except DataError as exc:
                    skipped[day] = str(exc)
                else:
                    state, row = _simulate_day(
                        spec, state, day, day_prices, forecast, dt, config, frames
                    )
        state = age(spec, state, hours=24.0)
        if row is not None:
            daily[day] = {**row, "soh": state.soh}

    if not daily:
        raise DataError(f"no days to simulate for {forecaster.name}; skipped {len(skipped)}")
    return BacktestResult(
        spec=spec,
        intervals=pd.concat(frames),
        daily=pd.DataFrame.from_dict(daily, orient="index", columns=DAILY_COLUMNS),
        skipped=skipped,
        final_state=state,
        forecaster=forecaster.name,
        currency=prices.currency,
        step_hours=dt,
    )


def _simulate_day(
    spec: BatterySpec,
    state: BatteryState,
    day: date,
    day_prices: pd.Series[float],
    forecast: np.ndarray[tuple[int], np.dtype[np.float64]],
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


def _calendar(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]
