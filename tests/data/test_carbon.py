from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from openenergy import DataError
from openenergy.data import (
    CARBON_ATTRIBUTION,
    CarbonIntensitySource,
    IntensitySeries,
    OPSDCsvSource,
    fill_gaps,
)

ROOT = Path(__file__).parents[2]
BUNDLED_CARBON = ROOT / "data/carbon_intensity/gb_national.csv"
BUNDLED_OPSD = ROOT / "data/time_series/time_series_60min_singleindex_filtered.csv"


def write_carbon(
    path: Path, actual: list[float | None], forecast: list[float] | None = None
) -> Path:
    index = pd.date_range("2019-01-01", periods=len(actual), freq="30min", tz="UTC")
    pd.DataFrame(
        {
            "utc_timestamp": index.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "forecast": forecast if forecast is not None else [200.0] * len(actual),
            "actual": actual,
        }
    ).to_csv(path, index=False)
    return path


def test_loads_half_hourly_actual(tmp_path: Path) -> None:
    source = CarbonIntensitySource(write_carbon(tmp_path / "ci.csv", [100.0, 200.0, 300.0, 400.0]))
    series = source.intensity()
    assert isinstance(series, IntensitySeries)
    assert series.kind == "actual"
    assert series.step_hours == 0.5
    assert series.values.tolist() == [100.0, 200.0, 300.0, 400.0]
    assert series.rejected == 0


def test_resamples_to_hourly_mean(tmp_path: Path) -> None:
    source = CarbonIntensitySource(write_carbon(tmp_path / "ci.csv", [100.0, 200.0, 300.0, 400.0]))
    hourly = source.intensity(step=pd.Timedelta(hours=1))
    assert hourly.values.tolist() == [150.0, 350.0]
    assert hourly.step_hours == 1.0


def test_hour_with_a_missing_half_is_missing(tmp_path: Path) -> None:
    source = CarbonIntensitySource(write_carbon(tmp_path / "ci.csv", [100.0, None, 300.0, 400.0]))
    hourly = source.intensity(step=pd.Timedelta(hours=1))
    assert np.isnan(hourly.values.iloc[0])
    assert hourly.values.iloc[1] == 350.0


def test_rejects_impossible_values(tmp_path: Path) -> None:
    path = write_carbon(tmp_path / "ci.csv", [100.0] * 4, forecast=[100.0, 13579.0, -5.0, 120.0])
    series = CarbonIntensitySource(path).intensity(kind="forecast")
    assert series.rejected == 2
    assert series.values.isna().sum() == 2


def test_filters_inclusive_days(tmp_path: Path) -> None:
    path = write_carbon(tmp_path / "ci.csv", [100.0] * 96)
    series = CarbonIntensitySource(path).intensity(start=date(2019, 1, 2), end=date(2019, 1, 2))
    assert len(series.values) == 48


def test_unknown_kind_and_missing_file(tmp_path: Path) -> None:
    source = CarbonIntensitySource(write_carbon(tmp_path / "ci.csv", [100.0, 200.0]))
    with pytest.raises(DataError, match="kind"):
        source.intensity(kind="marginal")
    with pytest.raises(DataError, match="not found"):
        CarbonIntensitySource(tmp_path / "missing.csv").intensity()


def test_step_must_be_a_multiple(tmp_path: Path) -> None:
    source = CarbonIntensitySource(write_carbon(tmp_path / "ci.csv", [100.0] * 4))
    with pytest.raises(DataError, match="multiple"):
        source.intensity(step=pd.Timedelta(minutes=45))


def test_fill_gaps_on_intensity(tmp_path: Path) -> None:
    source = CarbonIntensitySource(write_carbon(tmp_path / "ci.csv", [100.0, None, 300.0]))
    filled, count = fill_gaps(source.intensity(), max_gap_hours=1)
    assert isinstance(filled, IntensitySeries)
    assert count == 1
    assert filled.values.tolist() == [100.0, 200.0, 300.0]


def test_attribution_names_neso() -> None:
    assert "National Energy System Operator" in CARBON_ATTRIBUTION
    assert "CC BY 4.0" in CARBON_ATTRIBUTION


@pytest.mark.skipif(not BUNDLED_CARBON.exists(), reason="bundled carbon extract not present")
def test_bundled_carbon_intensity() -> None:
    source = CarbonIntensitySource(BUNDLED_CARBON)
    actual = source.intensity()
    assert len(actual.values) == 48192
    assert actual.values.isna().sum() == 438
    assert source.intensity(kind="forecast").rejected == 16
    hourly = source.intensity(
        start=date(2019, 1, 1), end=date(2019, 12, 31), step=pd.Timedelta(hours=1)
    )
    assert len(hourly.values) == 8760
    assert hourly.values.mean() == pytest.approx(214.0, abs=0.5)


def write_opsd(path: Path) -> Path:
    index = pd.date_range("2019-01-01", periods=48, freq="h", tz="UTC")
    pd.DataFrame(
        {
            "utc_timestamp": index.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "GB_GBN_load_actual_entsoe_transparency": 30000.0,
            "GB_GBN_wind_generation_actual": 5000.0,
            "GB_GBN_solar_generation_actual": np.tile(np.r_[np.zeros(12), np.full(12, 2000.0)], 2),
        }
    ).to_csv(path, index=False)
    return path


def test_opsd_load_and_generation(tmp_path: Path) -> None:
    source = OPSDCsvSource(write_opsd(tmp_path / "ts.csv"))
    load = source.load("GB_GBN")
    wind = source.generation("GB_GBN", "wind", date(2019, 1, 2), date(2019, 1, 2))
    assert load.name == "load_mw"
    assert load.iloc[0] == 30000.0
    assert len(wind) == 24
    assert source.series("GB_GBN_solar_generation_actual").max() == 2000.0


def test_opsd_missing_column_lists_suggestions(tmp_path: Path) -> None:
    source = OPSDCsvSource(write_opsd(tmp_path / "ts.csv"))
    with pytest.raises(DataError, match="GB_GBN_hydro_generation_actual"):
        source.generation("GB_GBN", "hydro")


@pytest.mark.skipif(not BUNDLED_OPSD.exists(), reason="bundled OPSD extract not present")
def test_bundled_gb_load() -> None:
    load = OPSDCsvSource(BUNDLED_OPSD).load("GB_GBN", date(2019, 1, 1), date(2019, 12, 31))
    assert len(load) == 8760
    assert 25_000 < load.mean() < 35_000
