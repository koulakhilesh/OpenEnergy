"""Gradient-boosted price forecaster (requires the ``openenergy[forecast]`` extra)."""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from openenergy.errors import ConfigError, DataError

FloatArray = npt.NDArray[np.float64]

LAG_DAYS = {"lag_1d": 1, "lag_2d": 2, "lag_7d": 7, "lag_14d": 14}
MIN_TRAINING_INTERVALS = 48


def make_features(
    index: pd.DatetimeIndex, prices: pd.Series[float], lead_hours: float
) -> pd.DataFrame:
    """Calendar and lagged-price features; lags at or after the decision time are NaN.

    The decision time for an interval is its UTC day start minus ``lead_hours``, matching
    the backtest, so training rows see exactly what a live forecast would.
    """
    decision = index.normalize() - pd.Timedelta(hours=lead_hours)
    features = pd.DataFrame(
        {
            "hour": index.hour + index.minute / 60,
            "dayofweek": index.dayofweek,
            "month": index.month,
            "weekend": (index.dayofweek >= 5).astype(int),
        },
        index=index,
    )
    for column, days in LAG_DAYS.items():
        source = index - pd.Timedelta(days=days)
        values = np.array(prices.reindex(source), dtype=np.float64)
        values[source >= decision] = np.nan
        features[column] = values
    return features


class GradientBoostingForecaster:
    """Histogram gradient boosting on calendar and lagged prices, trained chronologically."""

    name = "gradient_boosting"

    def __init__(
        self,
        lead_hours: float = 12.0,
        max_iter: int = 300,
        learning_rate: float = 0.05,
        seed: int = 0,
    ) -> None:
        if not (math.isfinite(lead_hours) and lead_hours >= 0):
            raise ConfigError(f"lead_hours must be non-negative, got {lead_hours}")
        self._lead_hours = lead_hours
        # No early stopping: its random validation split would mix future and past rows.
        self._model = HistGradientBoostingRegressor(
            max_iter=max_iter,
            learning_rate=learning_rate,
            early_stopping=False,
            random_state=seed,
        )
        self._train_end: pd.Timestamp | None = None

    def fit(self, prices: pd.Series[float]) -> GradientBoostingForecaster:
        """Train on every interval of ``prices``; forecasts must start after its last timestamp."""
        observed = prices.notna()
        if int(observed.sum()) < MIN_TRAINING_INTERVALS:
            raise DataError(
                f"need at least {MIN_TRAINING_INTERVALS} training prices, got {int(observed.sum())}"
            )
        index = pd.DatetimeIndex(prices.index)
        features = make_features(index, prices, self._lead_hours)
        # Hourly datasets are small; OpenMP threading costs far more than it saves here.
        with threadpool_limits(limits=1, user_api="openmp"):
            self._model.fit(features[observed.to_numpy()], prices[observed])
        self._train_end = index.max()
        return self

    def forecast(self, history: pd.Series[float], index: pd.DatetimeIndex) -> FloatArray:
        if self._train_end is None:
            raise ConfigError("call fit() before forecast()")
        if index[0] <= self._train_end:
            raise DataError(
                f"forecast window {index[0]} overlaps training data ending {self._train_end}"
            )
        features = make_features(index, history, self._lead_hours)
        with threadpool_limits(limits=1, user_api="openmp"):
            predicted = self._model.predict(features)
        return np.asarray(predicted, dtype=np.float64)
