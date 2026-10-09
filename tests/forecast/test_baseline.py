import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError, DataError
from openenergy.data import PriceSeries
from openenergy.forecast import Forecaster, NaiveLastWeek, NoisyForesight, PerfectForesight


def series(days: int = 21, start: str = "2019-01-01") -> PriceSeries:
    index = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    return PriceSeries(pd.Series(np.arange(days * 24, dtype=float), index=index), "GBP", "GB")


def day_index(day: str) -> pd.DatetimeIndex:
    return pd.date_range(day, periods=24, freq="h", tz="UTC")


def history_before(actual: PriceSeries, cutoff: str) -> pd.Series:
    prices = actual.prices
    return prices[prices.index < pd.Timestamp(cutoff, tz="UTC")]


def test_all_satisfy_protocol() -> None:
    actual = series()
    forecasters: list[Forecaster] = [
        PerfectForesight(actual),
        NaiveLastWeek(),
        NoisyForesight(actual, error_std=1.0),
    ]
    assert [f.name for f in forecasters] == [
        "perfect_foresight",
        "naive_last_week",
        "noisy_foresight",
    ]


def test_perfect_foresight_returns_actual() -> None:
    actual = series()
    index = day_index("2019-01-10")
    result = PerfectForesight(actual).forecast(pd.Series(dtype=float), index)
    assert result.tolist() == actual.prices.loc[index].tolist()


def test_perfect_foresight_requires_coverage() -> None:
    with pytest.raises(DataError, match="actual prices"):
        PerfectForesight(series(days=2)).forecast(pd.Series(dtype=float), day_index("2019-02-01"))


def test_naive_last_week_uses_same_hour_seven_days_earlier() -> None:
    actual = series()
    history = history_before(actual, "2019-01-09 12:00")
    result = NaiveLastWeek().forecast(history, day_index("2019-01-10"))
    expected = actual.prices.loc[day_index("2019-01-03")].to_numpy()
    assert result.tolist() == expected.tolist()


def test_naive_last_week_falls_back_to_two_weeks() -> None:
    actual = series()
    history = history_before(actual, "2019-01-16 12:00").copy()
    history.loc[day_index("2019-01-10")[:3]] = np.nan
    result = NaiveLastWeek().forecast(history, day_index("2019-01-17"))
    expected = actual.prices.loc[day_index("2019-01-10")].to_numpy().copy()
    expected[:3] = actual.prices.loc[day_index("2019-01-03")[:3]].to_numpy()
    assert result.tolist() == expected.tolist()


def test_naive_last_week_raises_without_history() -> None:
    history = history_before(series(), "2019-01-03 12:00")
    with pytest.raises(DataError, match="2019-01-04"):
        NaiveLastWeek().forecast(history, day_index("2019-01-04"))


def test_naive_last_week_rejects_lookahead_history() -> None:
    actual = series()
    with pytest.raises(DataError, match="after"):
        NaiveLastWeek().forecast(actual.prices, day_index("2019-01-10"))


def test_noisy_foresight_zero_error_is_perfect() -> None:
    actual = series()
    index = day_index("2019-01-10")
    result = NoisyForesight(actual, error_std=0.0).forecast(pd.Series(dtype=float), index)
    assert result.tolist() == actual.prices.loc[index].tolist()


def test_noisy_foresight_is_reproducible_and_order_independent() -> None:
    actual = series()
    a, b = day_index("2019-01-10"), day_index("2019-01-11")
    first = NoisyForesight(actual, error_std=5.0, seed=3)
    second = NoisyForesight(actual, error_std=5.0, seed=3)
    empty = pd.Series(dtype=float)
    a1, b1 = first.forecast(empty, a), first.forecast(empty, b)
    b2, a2 = second.forecast(empty, b), second.forecast(empty, a)
    assert a1.tolist() == a2.tolist()
    assert b1.tolist() == b2.tolist()


def test_noisy_foresight_error_has_requested_spread() -> None:
    actual = series(days=400)
    forecaster = NoisyForesight(actual, error_std=10.0, seed=1)
    empty = pd.Series(dtype=float)
    errors = np.concatenate(
        [
            forecaster.forecast(empty, idx) - actual.prices.loc[idx].to_numpy()
            for idx in (
                day_index(str(day.date())) for day in pd.date_range("2019-01-01", periods=400)
            )
        ]
    )
    assert abs(errors.mean()) < 0.5
    assert errors.std() == pytest.approx(10.0, rel=0.05)


def test_noisy_foresight_days_differ() -> None:
    actual = series()
    forecaster = NoisyForesight(actual, error_std=5.0)
    empty = pd.Series(dtype=float)
    a, b = day_index("2019-01-10"), day_index("2019-01-11")
    noise_a = forecaster.forecast(empty, a) - actual.prices.loc[a].to_numpy()
    noise_b = forecaster.forecast(empty, b) - actual.prices.loc[b].to_numpy()
    assert not np.allclose(noise_a, noise_b)


def test_noisy_foresight_rejects_negative_error() -> None:
    with pytest.raises(ConfigError, match="error_std"):
        NoisyForesight(series(), error_std=-1.0)
