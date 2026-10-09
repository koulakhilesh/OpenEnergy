"""Baseline price forecasters."""

from __future__ import annotations

from typing import Protocol

import numpy as np
import numpy.typing as npt
import pandas as pd

from openenergy.data.series import PriceSeries
from openenergy.errors import ConfigError, DataError

FloatArray = npt.NDArray[np.float64]

_WEEK = pd.Timedelta(days=7)


class Forecaster(Protocol):
    """Predicts prices for ``index`` from ``history`` observed before the decision time."""

    @property
    def name(self) -> str: ...

    def forecast(self, history: pd.Series[float], index: pd.DatetimeIndex) -> FloatArray: ...


class PerfectForesight:
    """Returns the actual prices; the upper-bound benchmark."""

    name = "perfect_foresight"

    def __init__(self, actual: PriceSeries) -> None:
        self._actual = actual.prices

    def forecast(self, history: pd.Series[float], index: pd.DatetimeIndex) -> FloatArray:
        values = np.asarray(self._actual.reindex(index), dtype=np.float64)
        if np.isnan(values).any():
            raise DataError(f"actual prices missing for {index[0].date()}")
        return values


class NaiveLastWeek:
    """Same interval one week earlier, or two weeks earlier where that is missing."""

    name = "naive_last_week"

    def forecast(self, history: pd.Series[float], index: pd.DatetimeIndex) -> FloatArray:
        if not history.empty and history.index.max() >= index[0]:
            raise DataError(f"history extends to or after forecast start {index[0]}")
        values = np.array(history.reindex(index - _WEEK), dtype=np.float64)
        missing = np.isnan(values)
        if missing.any():
            fallback = np.asarray(history.reindex(index - 2 * _WEEK), dtype=np.float64)
            values[missing] = fallback[missing]
        if np.isnan(values).any():
            raise DataError(f"no price history one or two weeks before {index[0].date()}")
        return values


class NoisyForesight:
    """Actual prices plus Gaussian error, seeded per forecast window for reproducibility."""

    name = "noisy_foresight"

    def __init__(self, actual: PriceSeries, error_std: float, seed: int = 0) -> None:
        if not error_std >= 0:
            raise ConfigError(f"error_std must be non-negative, got {error_std}")
        self._perfect = PerfectForesight(actual)
        self._error_std = error_std
        self._seed = seed

    def forecast(self, history: pd.Series[float], index: pd.DatetimeIndex) -> FloatArray:
        values = self._perfect.forecast(history, index)
        window = int(index[0].timestamp()) % 2**63
        rng = np.random.default_rng([self._seed, window])
        return values + rng.normal(0.0, self._error_std, size=values.size)
