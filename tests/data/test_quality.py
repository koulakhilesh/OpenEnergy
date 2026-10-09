import numpy as np
import pandas as pd

from openenergy.data.quality import flag_glitches


def demand(days: int = 10) -> pd.Series:
    index = pd.date_range("2019-01-01", periods=days * 24, freq="h", tz="UTC")
    hour = np.arange(index.size) % 24
    return pd.Series(30000 + 8000 * np.sin((hour - 6) * np.pi / 12), index=index)


def test_smooth_series_is_untouched() -> None:
    assert not flag_glitches(demand()).any()


def test_isolated_spike_and_two_hour_dip_are_flagged() -> None:
    values = demand()
    values.iloc[50] += 15000
    values.iloc[[120, 121]] *= 0.5
    flagged = flag_glitches(values)
    assert flagged.iloc[50]
    assert flagged.iloc[120] and flagged.iloc[121]
    assert flagged.sum() == 3


def test_long_dropout_is_flagged_by_weekly_floor() -> None:
    values = demand()
    values.iloc[100:110] = 600.0
    flagged = flag_glitches(values)
    assert flagged.iloc[100:110].all()


def test_steep_genuine_ramp_is_kept() -> None:
    index = pd.date_range("2019-01-01", periods=48, freq="h", tz="UTC")
    ramp = pd.Series(
        np.r_[np.full(20, 20000.0), np.linspace(20000, 45000, 8), np.full(20, 45000.0)], index=index
    )
    assert not flag_glitches(ramp).any()
