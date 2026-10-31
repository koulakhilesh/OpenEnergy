"""Day-ahead price forecast from open fundamentals (requires the ``openenergy[forecast]`` extra).

What is known when the plan is fixed: the system operator's demand and wind forecasts for
the day, the gas price two days before, and the prices the auction has already published.
A gradient-boosted model, retrained every month on everything known by then, predicts each
hour's price relative to the last known 24-hour mean, which carries over a new price level
(2021-2022) that trees could not extrapolate. Each month it also chooses how far to stretch
the day's predicted shape around its mean: the stretch that would have earned a reference
battery most over the previous 90 days, judged on forecasts made without those days.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from openenergy.assets.battery import BatterySpec
from openenergy.backtest.engine import known_until
from openenergy.data.fundamentals import FUNDAMENTALS_FROM, FundamentalsSource
from openenergy.dispatch.arbitrage import DispatchConfig, optimise_dispatch
from openenergy.errors import ConfigError, DataError

FloatArray = npt.NDArray[np.float64]
Information = Literal["auction", "decision"]

TRAIN_FROM = FUNDAMENTALS_FROM
MIN_TRAINING_DAYS = 90
STRETCH_DAYS = 90
STRETCHES = (1.0, 1.25, 1.5, 1.75, 2.0)
LAG_DAYS = (1, 2, 7)
REFERENCE_BATTERY = BatterySpec(power_mw=1.0, energy_mwh=2.0)
REFERENCE_DISPATCH = DispatchConfig(degradation_cost=5.0)
_HOUR = pd.Timedelta(hours=1)
_DAY = pd.Timedelta(days=1)


@dataclass(frozen=True)
class MonthModel:
    """The model used for one month's forecasts and the stretch chosen for it."""

    model: HistGradientBoostingRegressor
    stretch: float
    trained_until: pd.Timestamp


class FundamentalsForecaster:
    """Forecasts from demand, wind, gas and published prices; retrained each month.

    ``stretch`` is ``"auto"`` (chosen monthly, see the module docstring) or a fixed factor.
    Forecasts use only ``history`` (prices known at the decision) and fundamentals issued by
    the decision, so the same calls in a backtest always give the same forecasts.
    """

    name = "fundamentals"

    def __init__(
        self,
        source: FundamentalsSource,
        lead_hours: float = 12.0,
        information: Information = "auction",
        stretch: float | Literal["auto"] = "auto",
        max_iter: int = 300,
        learning_rate: float = 0.05,
        seed: int = 0,
    ) -> None:
        if not (math.isfinite(lead_hours) and lead_hours >= 0):
            raise ConfigError(f"lead_hours must be non-negative, got {lead_hours}")
        if stretch != "auto" and not (isinstance(stretch, int | float) and stretch > 0):
            raise ConfigError(f"stretch must be 'auto' or a positive number, got {stretch!r}")
        self.source = source
        self.lead_hours = lead_hours
        self.information: Information = information
        self.stretch = stretch
        self._params = {"max_iter": max_iter, "learning_rate": learning_rate, "seed": seed}
        self.months: dict[pd.Timestamp, MonthModel] = {}
        self._cache: pd.DataFrame | None = None

    def forecast(self, history: pd.Series[float], index: pd.DatetimeIndex) -> FloatArray:
        day = index[0].normalize()
        cutoff = known_until(day, self.lead_hours, self.information)
        if not history.empty and history.index.max() >= cutoff:
            raise DataError(f"history extends to or after what is known for {day.date()}")
        if len(index) % 24 or (len(index) > 1 and index[1] - index[0] != _HOUR):
            raise ConfigError("the fundamentals forecast needs hourly prices for whole days")
        month = day.replace(day=1)
        if month not in self.months:
            self.months[month] = self._month(history, month)
        chosen = self.months[month]
        decision = day - pd.Timedelta(hours=self.lead_hours)
        frame = self.features(
            history,
            index,
            pd.DatetimeIndex([cutoff] * len(index)),
            pd.DatetimeIndex([decision] * len(index)),
        )
        if np.isnan(frame["level"]).any():
            raise DataError(f"no prices known in the 24 hours before {cutoff}")
        return _stretch(self._predict(chosen.model, frame), index, chosen.stretch)

    def features(
        self,
        prices: pd.Series[float],
        index: pd.DatetimeIndex,
        cutoff: pd.DatetimeIndex,
        decision: pd.DatetimeIndex,
    ) -> pd.DataFrame:
        """Model inputs for each timestamp, from prices before its ``cutoff`` and fundamentals
        issued by its ``decision``."""
        rolling = prices.rolling(24, min_periods=12).mean()
        level = np.asarray(rolling.reindex(cutoff - _HOUR), dtype=np.float64)
        frame = pd.DataFrame(
            {"hour": index.hour, "dayofweek": index.dayofweek, "month": index.month},
            index=index,
        )
        frame["level"] = level
        for days in LAG_DAYS:
            source = index - pd.Timedelta(days=days)
            values = np.array(prices.reindex(source), dtype=np.float64)
            values[np.asarray(source >= cutoff)] = np.nan
            frame[f"lag_{days}d"] = values - level
        wind = self.source.wind(index, decision)
        demand = self.source.demand(index, decision)
        frame["wind"] = wind
        frame["demand"] = demand
        frame["residual"] = demand - wind
        frame["wind_share"] = wind / demand
        frame["residual_vs_day"] = frame["residual"] - frame["residual"].groupby(
            index.normalize()
        ).transform("mean")
        frame["gas"] = self.source.gas(index, lag_days=2 + int(self.lead_hours // 24))
        return frame

    def _month(self, history: pd.Series[float], month: pd.Timestamp) -> MonthModel:
        until = known_until(month, self.lead_hours, self.information)
        model = self._fit(history, until)
        if self.stretch != "auto":
            return MonthModel(model, float(self.stretch), until)
        return MonthModel(model, self._choose_stretch(history, month), until)

    def _fit(self, history: pd.Series[float], until: pd.Timestamp) -> HistGradientBoostingRegressor:
        known = history[(history.index >= TRAIN_FROM - 8 * _DAY) & (history.index < until)]
        rows = pd.DatetimeIndex(known.index[known.index >= TRAIN_FROM])
        days = rows.normalize()
        if days.nunique() < MIN_TRAINING_DAYS:
            raise DataError(
                f"need {MIN_TRAINING_DAYS} days of prices from {TRAIN_FROM.date()} before "
                f"{until.date()} to train the fundamentals forecast, got {days.nunique()}"
            )
        frame = self._training_frame(known, rows)
        target = known.reindex(rows).to_numpy(dtype=np.float64) - frame["level"].to_numpy()
        usable = np.isfinite(target)
        model = HistGradientBoostingRegressor(
            max_iter=int(self._params["max_iter"]),
            learning_rate=float(self._params["learning_rate"]),
            early_stopping=False,
            random_state=int(self._params["seed"]),
        )
        with threadpool_limits(limits=1, user_api="openmp"):
            model.fit(frame[usable], target[usable])
        return model

    def _training_frame(self, known: pd.Series[float], rows: pd.DatetimeIndex) -> pd.DataFrame:
        # A row's inputs depend only on what was known at its own decision, so they are
        # computed once and reused by every later month's training.
        missing = (
            rows
            if self._cache is None
            else pd.DatetimeIndex(rows.difference(pd.DatetimeIndex(self._cache.index)))
        )
        if len(missing):
            days = missing.normalize()
            cutoffs = {d: known_until(d, self.lead_hours, self.information) for d in days.unique()}
            cutoff = pd.DatetimeIndex([cutoffs[d] for d in days])
            decision = pd.DatetimeIndex(days - pd.Timedelta(hours=self.lead_hours))
            new = self.features(known, missing, cutoff, decision)
            self._cache = new if self._cache is None else pd.concat([self._cache, new]).sort_index()
        assert self._cache is not None
        return self._cache.reindex(rows)

    def _predict(self, model: HistGradientBoostingRegressor, frame: pd.DataFrame) -> FloatArray:
        with threadpool_limits(limits=1, user_api="openmp"):
            shape = np.asarray(model.predict(frame), dtype=np.float64)
        predicted: FloatArray = shape + frame["level"].to_numpy(dtype=np.float64)
        return predicted

    def _choose_stretch(self, history: pd.Series[float], month: pd.Timestamp) -> float:
        """The stretch that would have earned the reference battery most on the last 90 days."""
        start = month - STRETCH_DAYS * _DAY
        try:
            model = self._fit(history, known_until(start, self.lead_hours, self.information))
        except DataError:
            return 1.0
        actual = history[(history.index >= start) & (history.index < month)]
        stamps = pd.DatetimeIndex(actual.index)
        counts = actual.groupby(stamps.normalize()).count()
        days = pd.DatetimeIndex(counts.index[counts == 24])
        if days.empty:
            return 1.0
        rows = pd.DatetimeIndex(stamps[stamps.normalize().isin(days)])
        known = history[history.index < known_until(month, self.lead_hours, self.information)]
        frame = self._training_frame(known, rows)
        if frame["level"].isna().any():
            keep = frame["level"].notna().to_numpy()
            frame, rows = frame[keep], rows[keep]
        forecast = self._predict(model, frame)
        prices = np.asarray(actual.reindex(rows), dtype=np.float64)
        earned = {
            k: _reference_revenue(_stretch(forecast, rows, k), prices, rows) for k in STRETCHES
        }
        return max(STRETCHES, key=lambda k: (earned[k], -k))


def _stretch(forecast: FloatArray, index: pd.DatetimeIndex, factor: float) -> FloatArray:
    """Scale each day's forecast around its daily mean."""
    if factor == 1.0:
        return forecast
    series = pd.Series(forecast, index=index)
    mean = series.groupby(index.normalize()).transform("mean").to_numpy(dtype=np.float64)
    stretched: FloatArray = mean + factor * (forecast - mean)
    return stretched


def _reference_revenue(forecast: FloatArray, prices: FloatArray, index: pd.DatetimeIndex) -> float:
    """Revenue of the reference battery planned day by day on ``forecast``, at ``prices``."""
    spec, config = REFERENCE_BATTERY, REFERENCE_DISPATCH
    state = spec.initial_state()
    total = 0.0
    for start in range(0, len(index), 24):
        part = slice(start, start + 24)
        if len(index[part]) < 24 or not np.isfinite(forecast[part]).all():
            continue
        plan = optimise_dispatch(spec, state, forecast[part], 1.0, config)
        moved = plan.discharge_mw - plan.charge_mw
        wear = config.degradation_cost * float((plan.charge_mw + plan.discharge_mw).sum())
        total += float(prices[part] @ moved) - wear
    return total
