from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from openenergy import DataError
from openenergy.cli import app
from openenergy.data import PriceSeries, ProfileSeries
from openenergy.metrics import capture_by_year, capture_metrics


def hourly(values: list[float], start: str = "2019-01-01") -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="h", tz="UTC")
    return pd.Series(values, index=index, dtype=float)


def test_capture_metrics_by_hand() -> None:
    prices = PriceSeries(hourly([10.0, 20.0, 30.0, -10.0]), "GBP", "GB")
    generation = hourly([0.0, 1.0, 1.0, 1.0])
    m = capture_metrics(prices, generation, capacity_mw=1.0, label="test")
    assert m.label == "test"
    assert m.currency == "GBP"
    assert m.intervals == 4
    assert m.energy_mwh == pytest.approx(3.0)
    assert m.capacity_factor == pytest.approx(0.75)
    assert m.baseload_price == pytest.approx(12.5)
    assert m.revenue == pytest.approx(40.0)
    assert m.captured_price == pytest.approx(40.0 / 3)
    assert m.capture_rate == pytest.approx((40.0 / 3) / 12.5)
    assert m.negative_price_share == pytest.approx(1 / 3)


def test_half_hourly_energy() -> None:
    index = pd.date_range("2019-01-01", periods=4, freq="30min", tz="UTC")
    prices = PriceSeries(pd.Series(50.0, index=index), "GBP", "GB")
    m = capture_metrics(prices, pd.Series(2.0, index=index), capacity_mw=2.0)
    assert m.energy_mwh == pytest.approx(4.0)
    assert m.capacity_factor == pytest.approx(1.0)


def test_missing_values_are_excluded_together() -> None:
    prices = PriceSeries(hourly([10.0, np.nan, 30.0]), "GBP", "GB")
    generation = hourly([1.0, 1.0, np.nan])
    m = capture_metrics(prices, generation, capacity_mw=1.0)
    assert m.intervals == 1
    assert m.baseload_price == pytest.approx(10.0)


def test_no_generation_has_no_captured_price() -> None:
    prices = PriceSeries(hourly([10.0, 20.0]), "GBP", "GB")
    m = capture_metrics(prices, hourly([0.0, 0.0]), capacity_mw=1.0)
    assert m.captured_price is None
    assert m.capture_rate is None
    assert m.negative_price_share is None


def test_non_positive_baseload_has_no_capture_rate() -> None:
    prices = PriceSeries(hourly([-10.0, 5.0]), "GBP", "GB")
    m = capture_metrics(prices, hourly([1.0, 1.0]), capacity_mw=1.0)
    assert m.captured_price == pytest.approx(-2.5)
    assert m.capture_rate is None


def test_no_overlap_raises() -> None:
    prices = PriceSeries(hourly([10.0, 20.0]), "GBP", "GB")
    with pytest.raises(DataError, match="overlap"):
        capture_metrics(prices, hourly([1.0, 1.0], start="2020-01-01"), capacity_mw=1.0)


def test_capture_by_year_is_per_mw_installed() -> None:
    hours = 2 * 8760
    index = pd.date_range("2018-01-01", periods=hours, freq="h", tz="UTC")
    price = pd.Series(np.where(index.year == 2018, 40.0, 60.0), index=index)
    factor = pd.Series(np.where(index.hour < 12, 0.5, 0.0), index=index)
    years = capture_by_year(PriceSeries(price, "GBP", "GB"), ProfileSeries(factor, "solar", "GB"))
    assert [m.label for m in years] == ["2018", "2019"]
    assert years[0].capacity_factor == pytest.approx(0.25)
    assert years[1].captured_price == pytest.approx(60.0)
    assert years[0].energy_mwh == pytest.approx(8760 * 0.25)


def test_cli_capture(tmp_path: Path) -> None:
    index = pd.date_range("2019-01-01", periods=48, freq="h", tz="UTC")
    pd.DataFrame(
        {
            "utc_timestamp": index.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "GB_GBN_price_day_ahead": np.tile(np.r_[np.full(12, 30.0), np.full(12, 70.0)], 2),
            "GB_GBN_solar_profile": np.tile(np.r_[np.zeros(12), np.full(12, 0.5)], 2),
            "GB_GBN_wind_profile": 0.3,
        }
    ).to_csv(tmp_path / "ts.csv", index=False)
    result = CliRunner().invoke(app, ["capture", str(tmp_path / "ts.csv")])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0].split()[:2] == ["year", "technology"]
    solar = next(line for line in lines if " solar " in f" {line} ")
    assert "140.0%" in solar
    wind = next(line for line in lines if " wind " in f" {line} ")
    assert "100.0%" in wind


def test_cli_capture_single_technology(tmp_path: Path) -> None:
    index = pd.date_range("2019-01-01", periods=48, freq="h", tz="UTC")
    pd.DataFrame(
        {
            "utc_timestamp": index.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "GB_GBN_price_day_ahead": 50.0,
            "GB_GBN_solar_profile": 0.2,
            "GB_GBN_wind_profile": 0.3,
        }
    ).to_csv(tmp_path / "ts.csv", index=False)
    result = CliRunner().invoke(app, ["capture", str(tmp_path / "ts.csv"), "-t", "wind"])
    assert result.exit_code == 0, result.output
    assert "solar" not in result.output
    assert "wind" in result.output
