from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from openenergy import DataError
from openenergy.data import OPSDCsvSource, ProfileSeries, fill_gaps

BUNDLED = Path(__file__).parents[2] / "data/time_series/time_series_60min_singleindex_filtered.csv"


def hourly(values: list[float], start: str = "2019-01-01") -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="h", tz="UTC")
    return pd.Series(values, index=index, dtype=float)


def write_csv(path: Path) -> Path:
    index = pd.date_range("2019-01-01", periods=48, freq="h", tz="UTC")
    solar = np.tile(np.r_[np.zeros(6), np.linspace(0, 1.2, 12), np.zeros(6)], 2)
    solar[30] = np.nan
    pd.DataFrame(
        {
            "utc_timestamp": index.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "GB_GBN_price_day_ahead": 50.0,
            "GB_GBN_solar_profile": solar,
            "GB_GBN_wind_offshore_profile": 0.4,
            "GB_GBN_wind_offshore_capacity": 8000.0,
            "DE_LU_wind_profile": 0.3,
        }
    ).to_csv(path, index=False)
    return path


def test_profile_series_validates_range() -> None:
    with pytest.raises(DataError, match=r"\[0, 1\]"):
        ProfileSeries(hourly([0.5, 1.2]), technology="solar", zone="GB")
    with pytest.raises(DataError, match=r"\[0, 1\]"):
        ProfileSeries(hourly([0.5, -0.1]), technology="solar", zone="GB")


def test_profile_series_allows_missing_values() -> None:
    profile = ProfileSeries(hourly([0.5, np.nan, 0.2]), technology="wind", zone="GB")
    assert profile.values.isna().sum() == 1
    assert profile.step_hours == 1.0


def test_profile_series_rejects_non_utc() -> None:
    naive = pd.Series([0.1, 0.2], index=pd.date_range("2019-01-01", periods=2, freq="h"))
    with pytest.raises(DataError, match="UTC"):
        ProfileSeries(naive, technology="wind", zone="GB")


def test_profile_between_and_complete_days() -> None:
    values = [0.5] * 72
    values[30] = np.nan
    profile = ProfileSeries(hourly(values), technology="wind", zone="GB")
    assert profile.complete_days() == [date(2019, 1, 1), date(2019, 1, 3)]
    assert len(profile.between(date(2019, 1, 3), date(2019, 1, 3)).values) == 24


def test_fill_gaps_works_on_profiles() -> None:
    profile = ProfileSeries(hourly([0.2, np.nan, 0.4]), technology="wind", zone="GB")
    filled, count = fill_gaps(profile, max_gap_hours=2)
    assert isinstance(filled, ProfileSeries)
    assert count == 1
    assert filled.values.tolist() == pytest.approx([0.2, 0.3, 0.4])
    assert filled.technology == "wind"


def test_technologies_per_zone(tmp_path: Path) -> None:
    source = OPSDCsvSource(write_csv(tmp_path / "ts.csv"))
    assert source.technologies("GB_GBN") == ["solar", "wind_offshore"]
    assert source.technologies("DE_LU") == ["wind"]


def test_profile_clips_and_counts(tmp_path: Path) -> None:
    profile = OPSDCsvSource(write_csv(tmp_path / "ts.csv")).profile("GB_GBN", "solar")
    assert profile.technology == "solar"
    assert profile.zone == "GB_GBN"
    assert profile.values.max() == 1.0
    assert profile.clipped == 4
    assert profile.values.isna().sum() == 1


def test_profile_inclusive_days(tmp_path: Path) -> None:
    source = OPSDCsvSource(write_csv(tmp_path / "ts.csv"))
    profile = source.profile("GB_GBN", "wind_offshore", date(2019, 1, 2), date(2019, 1, 2))
    assert len(profile.values) == 24
    assert profile.clipped == 0


def test_unknown_technology_lists_available(tmp_path: Path) -> None:
    source = OPSDCsvSource(write_csv(tmp_path / "ts.csv"))
    with pytest.raises(DataError, match="solar, wind_offshore"):
        source.profile("GB_GBN", "hydro")


@pytest.mark.skipif(not BUNDLED.exists(), reason="bundled OPSD extract not present")
def test_bundled_gb_solar_2019() -> None:
    profile = OPSDCsvSource(BUNDLED).profile(
        "GB_GBN", "solar", date(2019, 1, 1), date(2019, 12, 31)
    )
    assert profile.clipped == 27
    assert len(profile.values) == 8760
    # Capacity is not published after 2019-12-30, so the last day has no profile.
    assert len(profile.complete_days()) == 364
    assert profile.values.mean() == pytest.approx(0.153, abs=0.002)
