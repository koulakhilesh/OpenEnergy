from datetime import date

import numpy as np
import pandas as pd
import pytest

from openenergy import DataError
from openenergy.data import PriceSeries, fill_gaps


def hourly(values: list[float], start: str = "2019-01-01") -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="h", tz="UTC")
    return pd.Series(values, index=index, dtype=float)


def test_step_and_periods_per_day() -> None:
    series = PriceSeries(hourly([1.0] * 48), currency="GBP", zone="GB_GBN")
    assert series.step == pd.Timedelta(hours=1)
    assert series.step_hours == 1.0
    assert series.periods_per_day == 24


def test_half_hourly_step() -> None:
    index = pd.date_range("2019-01-01", periods=48, freq="30min", tz="UTC")
    series = PriceSeries(pd.Series(1.0, index=index), currency="GBP", zone="GB")
    assert series.step_hours == 0.5
    assert series.periods_per_day == 48


@pytest.mark.parametrize(
    "index",
    [
        pd.date_range("2019-01-01", periods=3, freq="h"),
        pd.date_range("2019-01-01", periods=3, freq="h", tz="Europe/London"),
    ],
)
def test_rejects_non_utc_index(index: pd.DatetimeIndex) -> None:
    with pytest.raises(DataError, match="UTC"):
        PriceSeries(pd.Series(1.0, index=index), currency="GBP", zone="GB")


def test_rejects_non_datetime_index() -> None:
    with pytest.raises(DataError, match="DatetimeIndex"):
        PriceSeries(pd.Series([1.0, 2.0]), currency="GBP", zone="GB")


def test_rejects_duplicates() -> None:
    raw = hourly([1.0, 2.0, 3.0])
    dup = pd.concat([raw, raw.iloc[[1]]]).sort_index()
    with pytest.raises(DataError, match="duplicate"):
        PriceSeries(dup, currency="GBP", zone="GB")


def test_rejects_unsorted() -> None:
    with pytest.raises(DataError, match="increasing"):
        PriceSeries(hourly([1.0, 2.0, 3.0]).iloc[::-1], currency="GBP", zone="GB")


def test_rejects_irregular_grid() -> None:
    raw = hourly([1.0, 2.0, 3.0, 4.0]).drop(index=pd.Timestamp("2019-01-01 01:00", tz="UTC"))
    with pytest.raises(DataError, match="regular"):
        PriceSeries(raw, currency="GBP", zone="GB")


def test_rejects_step_not_dividing_day() -> None:
    index = pd.date_range("2019-01-01", periods=4, freq="7h", tz="UTC")
    with pytest.raises(DataError, match="divide"):
        PriceSeries(pd.Series(1.0, index=index), currency="GBP", zone="GB")


def test_rejects_too_short() -> None:
    with pytest.raises(DataError, match="at least two"):
        PriceSeries(hourly([1.0]), currency="GBP", zone="GB")


def test_rejects_bad_currency() -> None:
    with pytest.raises(DataError, match="currency"):
        PriceSeries(hourly([1.0, 2.0]), currency="pounds", zone="GB")


def test_between_is_inclusive_of_whole_days() -> None:
    series = PriceSeries(hourly(list(range(72))), currency="GBP", zone="GB")
    sliced = series.between(date(2019, 1, 2), date(2019, 1, 2))
    assert len(sliced.prices) == 24
    assert sliced.prices.iloc[0] == 24
    assert sliced.currency == "GBP"


def test_between_empty_raises() -> None:
    series = PriceSeries(hourly([1.0] * 24), currency="GBP", zone="GB")
    with pytest.raises(DataError, match="no data"):
        series.between(date(2020, 1, 1), date(2020, 1, 2))


def test_complete_days_excludes_partial_and_missing() -> None:
    values = [1.0] * 72 + [1.0] * 5
    values[30] = np.nan
    series = PriceSeries(hourly(values, start="2019-01-01"), currency="GBP", zone="GB")
    assert series.complete_days() == [date(2019, 1, 1), date(2019, 1, 3)]


def test_day_returns_single_day() -> None:
    series = PriceSeries(hourly(list(range(48))), currency="GBP", zone="GB")
    day = series.day(date(2019, 1, 2))
    assert len(day) == 24
    assert day.iloc[0] == 24


def test_prices_are_read_only_copy() -> None:
    raw = hourly([1.0, 2.0])
    series = PriceSeries(raw, currency="GBP", zone="GB")
    raw.iloc[0] = 99.0
    assert series.prices.iloc[0] == 1.0


def test_fill_gaps_interpolates_short_interior_runs() -> None:
    series = PriceSeries(hourly([10.0, np.nan, np.nan, 40.0, 50.0]), currency="GBP", zone="GB")
    filled, count = fill_gaps(series, max_gap_hours=2)
    assert count == 2
    assert filled.prices.tolist() == [10.0, 20.0, 30.0, 40.0, 50.0]


def test_fill_gaps_leaves_long_runs_untouched() -> None:
    series = PriceSeries(hourly([10.0, np.nan, np.nan, np.nan, 50.0]), currency="GBP", zone="GB")
    filled, count = fill_gaps(series, max_gap_hours=2)
    assert count == 0
    assert filled.prices.isna().sum() == 3


def test_fill_gaps_leaves_edges_untouched() -> None:
    series = PriceSeries(hourly([np.nan, 20.0, 30.0, np.nan]), currency="GBP", zone="GB")
    filled, count = fill_gaps(series, max_gap_hours=2)
    assert count == 0
    assert filled.prices.isna().sum() == 2


def test_fill_gaps_rejects_negative_limit() -> None:
    series = PriceSeries(hourly([1.0, 2.0]), currency="GBP", zone="GB")
    with pytest.raises(DataError, match="max_gap_hours"):
        fill_gaps(series, max_gap_hours=-1)
