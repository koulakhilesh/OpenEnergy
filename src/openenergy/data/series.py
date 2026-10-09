"""Validated time series (prices, capacity factors) on a regular UTC grid."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, overload

import pandas as pd

from openenergy.errors import DataError

if TYPE_CHECKING:
    from openenergy.data.carbon import IntensitySeries

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
        selected = _between(self.prices, start, end, self.zone)
        return PriceSeries(selected, currency=self.currency, zone=self.zone)

    def day(self, day: date) -> pd.Series[float]:
        """Return the prices for one UTC day; the day must be fully covered."""
        return _day(self.prices, day, self.periods_per_day, self.zone)

    def complete_days(self) -> list[date]:
        """UTC days with every interval present and no missing prices."""
        return _complete_days(self.prices, self.periods_per_day)


@dataclass(frozen=True, eq=False)
class ProfileSeries:
    """Capacity factors in [0, 1] for one technology; ``clipped`` counts values capped on load."""

    values: pd.Series[float] = field(repr=False)
    technology: str
    zone: str
    clipped: int = 0
    step: pd.Timedelta = field(init=False)

    def __post_init__(self) -> None:
        values, step = _validate(self.values)
        if ((values < 0) | (values > 1)).any():
            raise DataError(f"{self.technology} capacity factors must lie in [0, 1]")
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "step", step)

    @property
    def step_hours(self) -> float:
        return float(self.step / _HOUR)

    @property
    def periods_per_day(self) -> int:
        return int(_DAY / self.step)

    def between(self, start: date | None = None, end: date | None = None) -> ProfileSeries:
        """Return the whole UTC days from ``start`` to ``end``, both inclusive."""
        selected = _between(self.values, start, end, self.zone)
        return dataclasses.replace(self, values=selected)

    def day(self, day: date) -> pd.Series[float]:
        """Return the capacity factors for one UTC day; the day must be fully covered."""
        return _day(self.values, day, self.periods_per_day, self.zone)

    def complete_days(self) -> list[date]:
        """UTC days with every interval present and no missing values."""
        return _complete_days(self.values, self.periods_per_day)


@overload
def fill_gaps(series: PriceSeries, max_gap_hours: float) -> tuple[PriceSeries, int]: ...
@overload
def fill_gaps(series: ProfileSeries, max_gap_hours: float) -> tuple[ProfileSeries, int]: ...
@overload
def fill_gaps(series: IntensitySeries, max_gap_hours: float) -> tuple[IntensitySeries, int]: ...
def fill_gaps(
    series: PriceSeries | ProfileSeries | IntensitySeries, max_gap_hours: float
) -> tuple[PriceSeries | ProfileSeries | IntensitySeries, int]:
    """Linearly interpolate interior gaps no longer than ``max_gap_hours``.

    Returns the filled series and the number of intervals filled.
    """
    if max_gap_hours < 0:
        raise DataError(f"max_gap_hours must be non-negative, got {max_gap_hours}")
    values = series.prices if isinstance(series, PriceSeries) else series.values
    missing = values.isna()
    first, last = values.first_valid_index(), values.last_valid_index()
    if first is None or last is None or not missing.any():
        return series, 0

    run_id = (missing != missing.shift()).cumsum()
    run_length = missing.groupby(run_id).transform("size")
    max_steps = int(max_gap_hours / series.step_hours)
    interior = (values.index > first) & (values.index < last)
    fillable = missing & (run_length <= max_steps) & interior
    filled = values.where(~fillable, values.interpolate(limit_area="inside"))
    count = int(fillable.sum())
    if isinstance(series, PriceSeries):
        return PriceSeries(filled, currency=series.currency, zone=series.zone), count
    return dataclasses.replace(series, values=filled), count


def _between(
    values: pd.Series[float], start: date | None, end: date | None, zone: str
) -> pd.Series[float]:
    index = values.index
    mask = pd.Series(True, index=index)
    if start is not None:
        mask &= index >= pd.Timestamp(start, tz="UTC")
    if end is not None:
        mask &= index < pd.Timestamp(end, tz="UTC") + _DAY
    selected = values[mask.to_numpy()]
    if selected.empty:
        raise DataError(f"no data between {start} and {end} for {zone}")
    return selected


def _day(values: pd.Series[float], day: date, periods: int, zone: str) -> pd.Series[float]:
    start = pd.Timestamp(day, tz="UTC")
    selected = values[(values.index >= start) & (values.index < start + _DAY)]
    if len(selected) != periods:
        raise DataError(f"{day} is not fully covered for {zone}")
    return selected


def _complete_days(values: pd.Series[float], periods: int) -> list[date]:
    days = pd.DatetimeIndex(values.index).normalize()
    counts = values.groupby(days).count()
    return [ts.date() for ts in counts.index[counts == periods]]


def _validate(values: pd.Series[float]) -> tuple[pd.Series[float], pd.Timedelta]:
    index = values.index
    if not isinstance(index, pd.DatetimeIndex):
        raise DataError("series must have a DatetimeIndex")
    if index.tz is None or str(index.tz) != "UTC":
        raise DataError(f"series index must be tz-aware UTC, got {index.tz}")
    if len(index) < 2:
        raise DataError("series needs at least two timestamps to define a step")
    if index.has_duplicates:
        raise DataError("series index has duplicate timestamps")
    if not index.is_monotonic_increasing:
        raise DataError("series index must be strictly increasing")

    steps = index[1:] - index[:-1]
    step = steps[0]
    if (steps != step).any():
        raise DataError("series must be on a regular time grid")
    if _DAY % step != pd.Timedelta(0):
        raise DataError(f"step {step} must divide one day evenly")

    try:
        numeric = values.astype(float)
    except (TypeError, ValueError) as exc:
        raise DataError(f"series values must be numeric: {exc}") from exc
    return numeric.copy(), step
