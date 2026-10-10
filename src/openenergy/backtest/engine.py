"""Rolling day-ahead backtest: plan on forecasts, settle at actual prices."""

from __future__ import annotations

import dataclasses
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
from openenergy.forecast.baseline import Forecaster, NaiveLastWeek

FloatArray = npt.NDArray[np.float64]
CARBON_PLANNING = ("last_week", "actual")

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


@dataclass(frozen=True, eq=False)
class Carbon:
    """Actual grid carbon intensity (gCO2/kWh) for accounting and, with a price, for dispatch.

    ``planning`` sets what dispatch sees: ``last_week`` uses the same interval a week earlier
    (two weeks if missing), cut off at the decision time like prices; ``actual`` uses the
    real values and is an upper bound. NESO's archived "forecast" is not used: it is the
    last forecast before each half-hour, so planning on it the day before would look ahead.
    Reported money stays market revenue.
    """

    actual: pd.Series[float]
    price_per_t: float = 0.0
    planning: str = "last_week"

    def __post_init__(self) -> None:
        if not (math.isfinite(self.price_per_t) and self.price_per_t >= 0):
            raise ConfigError(f"price_per_t must be non-negative, got {self.price_per_t}")
        if self.planning not in CARBON_PLANNING:
            raise ConfigError(
                f"planning must be one of {', '.join(CARBON_PLANNING)}, got {self.planning!r}"
            )


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
    carbon: Carbon | None = None


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
    carbon: Carbon | None = None,
) -> BacktestResult:
    """Simulate each UTC day in order; the battery ages through every calendar day in range.

    With a ``site``, the battery shares a grid connection with renewable output. With
    ``carbon``, emissions are reported and a carbon price steers dispatch.
    """
    config = config or BacktestConfig()
    dt = prices.step_hours
    state = spec.initial_state()
    frames: list[pd.DataFrame] = []
    daily: dict[date, dict[str, float]] = {}
    skipped: dict[date, str] = {}
    available = None if site is None else _on_grid(site.available_mw, prices)
    required = [] if available is None else [available]
    actual_ci = None
    if carbon is not None:
        actual_ci = carbon.actual.reindex(prices.prices.index)
        required.append(actual_ci)

    lookahead = config.dispatch.lookahead_days
    for day, step in _days(prices, forecaster, config, days, required, lookahead):
        row: dict[str, float] | None = None
        if isinstance(step, str):
            skipped[day] = step
        elif step is not None:
            day_prices, forecast = step
            horizon = _horizon(day_prices, forecast.size)
            planning: FloatArray | str = forecast
            if carbon is not None and actual_ci is not None and carbon.price_per_t > 0:
                planning = _carbon_priced(forecast, horizon, actual_ci, carbon, config)
            if isinstance(planning, str):
                skipped[day] = planning
            elif site is None or available is None:
                state, row = _battery_day(
                    spec, state, day, day_prices, forecast, planning, dt, config, frames
                )
            else:
                output = np.asarray(available.loc[horizon], dtype=np.float64)
                state, row = _site_day(
                    spec,
                    state,
                    site.grid,
                    day,
                    day_prices,
                    forecast,
                    planning,
                    output,
                    dt,
                    config,
                    frames,
                )
            if actual_ci is not None and row is not None:
                _add_emissions(frames[-1], row, actual_ci, dt)
        state = age(spec, state, hours=24.0)
        if row is not None:
            daily[day] = {**row, "soh": state.soh}

    if not daily:
        raise DataError(f"no days to simulate for {forecaster.name}; skipped {len(skipped)}")
    columns = list(DAILY_COLUMNS if site is None else SITE_DAILY_COLUMNS)
    if carbon is not None:
        columns.append("emissions_t")
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
        carbon=carbon,
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
    for day, step in _days(prices, forecaster, config, days, [available]):
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
    required: list[pd.Series[float]],
    lookahead: int = 0,
) -> Iterator[tuple[date, str | tuple[pd.Series[float], FloatArray] | None]]:
    """Yield every calendar day in range with a skip reason, (prices, forecast), or None.

    None marks days outside the requested set; the battery still ages through them. A day
    is simulated only if prices and every ``required`` series cover it completely. The
    forecast covers the day and up to ``lookahead`` following days, fewer where a forecast
    or a ``required`` series is unavailable (for example at the end of the data).
    """
    actual = prices.prices
    index = pd.DatetimeIndex(actual.index)
    ppd = prices.periods_per_day
    covered = {ts.date() for ts in index.normalize().unique()}
    for series in required:
        counts = series.groupby(pd.DatetimeIndex(series.index).normalize()).count()
        covered &= {ts.date() for ts in counts.index[counts == ppd]}
    complete = covered & set(prices.complete_days())
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
            yield day, "incomplete or missing prices, plant output or carbon intensity"
        else:
            day_prices = prices.day(day)
            start = pd.Timestamp(day, tz="UTC")
            history = actual.iloc[: index.searchsorted(start - lead)]
            ahead = 0
            while ahead < lookahead and day + timedelta(days=ahead + 1) in covered:
                ahead += 1
            while True:
                horizon = pd.date_range(start, periods=ppd * (1 + ahead), freq=prices.step)
                try:
                    forecast = forecaster.forecast(history, horizon)
                except DataError as exc:
                    if ahead == 0:
                        yield day, str(exc)
                        break
                    ahead -= 1
                else:
                    yield day, (day_prices, forecast)
                    break


def _horizon(day_prices: pd.Series[float], periods: int) -> pd.DatetimeIndex:
    """The planning timestamps: the day's, extended on the same grid to ``periods``."""
    index = pd.DatetimeIndex(day_prices.index)
    return pd.date_range(index[0], periods=periods, freq=index[1] - index[0])


def _planning_config(config: BacktestConfig, periods: int, per_day: int) -> DispatchConfig:
    """Dispatch settings for a horizon of ``periods``: the cycle cap scales per day planned."""
    dispatch = config.dispatch
    if dispatch.max_cycles is None or periods == per_day:
        return dispatch
    return dataclasses.replace(dispatch, max_cycles=dispatch.max_cycles * periods / per_day)


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
    planning: FloatArray,
    dt: float,
    config: BacktestConfig,
    frames: list[pd.DataFrame],
) -> tuple[BatteryState, dict[str, float]]:
    n = len(day_prices)
    try:
        plan = optimise_dispatch(
            spec, state, planning, dt, _planning_config(config, planning.size, n)
        )
    except InfeasibleDispatchError as exc:
        raise InfeasibleDispatchError(f"{day}: {exc}") from exc
    charge, discharge, forecast = plan.charge_mw[:n], plan.discharge_mw[:n], forecast[:n]
    outcome = apply_dispatch(spec, state, charge, discharge, dt)
    price = np.asarray(day_prices, dtype=np.float64)
    revenue = price * (discharge - charge) * dt
    frames.append(
        pd.DataFrame(
            {
                "price": price,
                "forecast": forecast,
                "charge_mw": charge,
                "discharge_mw": discharge,
                "energy_mwh": outcome.energy_mwh[1:],
                "revenue": revenue,
            },
            index=day_prices.index,
        )
    )
    new = outcome.state
    row = {
        "revenue": float(revenue.sum()),
        "expected_revenue": float(forecast @ (discharge - charge) * dt),
        "charged_mwh": float(charge.sum() * dt),
        "discharged_mwh": float(discharge.sum() * dt),
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
    planning: FloatArray,
    available: FloatArray,
    dt: float,
    config: BacktestConfig,
    frames: list[pd.DataFrame],
) -> tuple[BatteryState, dict[str, float]]:
    n = len(day_prices)
    try:
        full: ColocatedPlan = optimise_colocated(
            spec,
            state,
            available,
            planning,
            dt,
            grid,
            _planning_config(config, planning.size, n),
        )
    except InfeasibleDispatchError as exc:
        raise InfeasibleDispatchError(f"{day}: {exc}") from exc
    plan = _first(full, n)
    available, forecast = available[:n], forecast[:n]
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
        "expected_revenue": float(forecast @ plan.export_mw * dt),
        "available_mwh": float(available.sum() * dt),
        "curtailed_mwh": float(plan.curtailed_mw.sum() * dt),
        "charged_mwh": float(plan.charge_mw.sum() * dt),
        "discharged_mwh": float(plan.discharge_mw.sum() * dt),
        "equivalent_cycles": new.equivalent_cycles,
        "energy_mwh": new.energy_mwh,
    }
    return new, row


def _first(plan: ColocatedPlan, n: int) -> ColocatedPlan:
    """The first ``n`` intervals of a plan (the day that is settled)."""
    return dataclasses.replace(
        plan,
        plant_to_grid_mw=plan.plant_to_grid_mw[:n],
        plant_to_battery_mw=plan.plant_to_battery_mw[:n],
        curtailed_mw=plan.curtailed_mw[:n],
        grid_to_battery_mw=plan.grid_to_battery_mw[:n],
        charge_mw=plan.charge_mw[:n],
        discharge_mw=plan.discharge_mw[:n],
        export_mw=plan.export_mw[:n],
        energy_mwh=plan.energy_mwh[: n + 1],
    )


def _carbon_priced(
    forecast: FloatArray,
    index: pd.DatetimeIndex,
    actual_ci: pd.Series[float],
    carbon: Carbon,
    config: BacktestConfig,
) -> FloatArray | str:
    """Planning price plus the carbon price on planned intensity, or a reason to skip the day."""
    if carbon.planning == "actual":
        ci = np.asarray(actual_ci.loc[index], dtype=np.float64)
    else:
        cutoff = index[0] - pd.Timedelta(hours=config.lead_hours)
        history = actual_ci[actual_ci.index < cutoff].dropna()
        try:
            ci = NaiveLastWeek().forecast(history, index)
        except DataError as exc:
            return f"carbon intensity: {exc}"
    return forecast + carbon.price_per_t * ci / 1000.0


def _add_emissions(
    frame: pd.DataFrame, row: dict[str, float], intensity: pd.Series[float], dt: float
) -> None:
    """Net emissions in tCO2: imports add grid emissions, exports displace them."""
    ci = np.asarray(intensity.loc[frame.index], dtype=np.float64)
    if "export_mw" in frame:
        export = frame["export_mw"].to_numpy(dtype=np.float64)
    else:
        export = (frame["discharge_mw"] - frame["charge_mw"]).to_numpy(dtype=np.float64)
    emissions = -ci * export * dt / 1000.0
    frame["intensity"] = ci
    frame["emissions_t"] = emissions
    row["emissions_t"] = float(emissions.sum())


def _calendar(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]
