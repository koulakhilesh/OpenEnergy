"""Validated price time series on a regular UTC grid."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from openenergy.errors import DataError

_DAY = pd.Timedelta(days=1)
_HOUR = pd.Timedelta(hours=1)
_CURRENCY = re.compile(r"[A-Z]{3}")


@dataclass(frozen=True, eq=False)
class PriceSeries:
    """Prices in currency/MWh, each timestamp labelling the start of its interval."""

    prices: pd.Series[float] = field(repr=False)
    currency: str
    zone: str
    step: pd.Timedelta = field(init=False)

    def __post_init__(self) -> None:
        prices, step = _validate(self.prices)
        if not _CURRENCY.fullmatch(self.currency):
            raise DataError(f"currency must be an ISO 4217 code, got {self.currency!r}")
        object.__setattr__(self, "prices", prices)
        object.__setattr__(self, "step", step)

    @property
    def step_hours(self) -> float:
        return float(self.step / _HOUR)

    @property
    def periods_per_day(self) -> int:
        return int(_DAY / self.step)

    def between(self, start: date | None = None, end: date | None = None) -> PriceSeries:
        """Return the whole UTC days from ``start`` to ``end``, both inclusive."""
        index = self.prices.index
        mask = pd.Series(True, index=index)
        if start is not None:
            mask &= index >= pd.Timestamp(start, tz="UTC")
        if end is not None:
            mask &= index < pd.Timestamp(end, tz="UTC") + _DAY
        selected = self.prices[mask.to_numpy()]
        if selected.empty:
            raise DataError(f"no data between {start} and {end} for {self.zone}")
        return PriceSeries(selected, currency=self.currency, zone=self.zone)

    def day(self, day: date) -> pd.Series[float]:
        """Return the prices for one UTC day; the day must be fully covered."""
        start = pd.Timestamp(day, tz="UTC")
        selected = self.prices[(self.prices.index >= start) & (self.prices.index < start + _DAY)]
        if len(selected) != self.periods_per_day:
            raise DataError(f"{day} is not fully covered for {self.zone}")
        return selected

    def complete_days(self) -> list[date]:
        """UTC days with every interval present and no missing prices."""
        days = pd.DatetimeIndex(self.prices.index).normalize()
        counts = self.prices.groupby(days).count()
        return [ts.date() for ts in counts.index[counts == self.periods_per_day]]


def fill_gaps(series: PriceSeries, max_gap_hours: float) -> tuple[PriceSeries, int]:
    """Linearly interpolate interior gaps no longer than ``max_gap_hours``.

    Returns the filled series and the number of intervals filled.
    """
    if max_gap_hours < 0:
        raise DataError(f"max_gap_hours must be non-negative, got {max_gap_hours}")
    prices = series.prices
    missing = prices.isna()
    first, last = prices.first_valid_index(), prices.last_valid_index()
    if first is None or last is None or not missing.any():
        return series, 0

    run_id = (missing != missing.shift()).cumsum()
    run_length = missing.groupby(run_id).transform("size")
    max_steps = int(max_gap_hours / series.step_hours)
    interior = (prices.index > first) & (prices.index < last)
    fillable = missing & (run_length <= max_steps) & interior

    filled = prices.where(~fillable, prices.interpolate(limit_area="inside"))
    return PriceSeries(filled, currency=series.currency, zone=series.zone), int(fillable.sum())


def _validate(prices: pd.Series[float]) -> tuple[pd.Series[float], pd.Timedelta]:
    index = prices.index
    if not isinstance(index, pd.DatetimeIndex):
        raise DataError("prices must have a DatetimeIndex")
    if index.tz is None or str(index.tz) != "UTC":
        raise DataError(f"prices index must be tz-aware UTC, got {index.tz}")
    if len(index) < 2:
        raise DataError("prices need at least two timestamps to define a step")
    if index.has_duplicates:
        raise DataError("prices index has duplicate timestamps")
    if not index.is_monotonic_increasing:
        raise DataError("prices index must be strictly increasing")

    steps = index[1:] - index[:-1]
    step = steps[0]
    if (steps != step).any():
        raise DataError("prices must be on a regular time grid")
    if _DAY % step != pd.Timedelta(0):
        raise DataError(f"step {step} must divide one day evenly")

    try:
        values = prices.astype(float)
    except (TypeError, ValueError) as exc:
        raise DataError(f"prices must be numeric: {exc}") from exc
    return values.copy(), step
