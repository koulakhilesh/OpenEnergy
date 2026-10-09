from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from openenergy import ConfigError, DataError
from openenergy.cli import app
from openenergy.data import OPSDCsvSource
from openenergy.system import (
    duration_curve,
    load_system,
    net_load,
    netload_by_year,
    surplus,
)


def frame(
    load: list[float], wind: list[float], solar: list[float], price: list[float] | None = None
) -> pd.DataFrame:
    index = pd.date_range("2019-01-01", periods=len(load), freq="h", tz="UTC")
    data = {"load_mw": load, "wind_mw": wind, "solar_mw": solar}
    data["price"] = price if price is not None else [50.0] * len(load)
    return pd.DataFrame(data, index=index, dtype=float)


def test_net_load_scales_renewables() -> None:
    system = frame([100, 100], [20, 40], [10, 0])
    assert net_load(system).tolist() == [70.0, 60.0]
    assert net_load(system, scale_wind=2, scale_solar=3).tolist() == [30.0, 20.0]


def test_net_load_rejects_negative_scale() -> None:
    with pytest.raises(ConfigError, match="scale"):
        net_load(frame([1], [1], [1]), scale_wind=-1)


def test_surplus_above_must_run_floor() -> None:
    net = pd.Series([50.0, 5.0, -10.0])
    assert surplus(net).tolist() == [0.0, 0.0, 10.0]
    assert surplus(net, must_run_mw=20).tolist() == [0.0, 15.0, 30.0]


def test_duration_curve_sorted_with_share_index() -> None:
    curve = duration_curve(pd.Series([3.0, 1.0, 2.0, 4.0]))
    assert curve.tolist() == [4.0, 3.0, 2.0, 1.0]
    assert curve.index.tolist() == [0.25, 0.5, 0.75, 1.0]


def test_yearly_stats_by_hand() -> None:
    system = frame(
        load=[100, 120, 90, 80],
        wind=[10, 10, 60, 90],
        solar=[0, 10, 10, 0],
        price=[60, 70, 20, 5],
    )
    (stats,) = netload_by_year(system, must_run_mw=0)
    assert stats.year == 2019
    assert stats.hours == 4
    assert stats.renewable_share == pytest.approx(190 / 390)
    assert stats.mean_net_mw == pytest.approx((90 + 100 + 20 - 10) / 4)
    assert stats.peak_net_mw == 100
    assert stats.min_net_mw == -10
    # |1h changes| are 10, 80, 30: the 99th percentile interpolates to 79.
    assert stats.ramp_1h_p99_mw == pytest.approx(79.0)
    assert stats.ramp_3h_p99_mw == pytest.approx(100.0)
    assert stats.surplus_mwh == pytest.approx(10.0)
    assert stats.surplus_hours == 1
    assert stats.surplus_share == pytest.approx(10 / 190)
    slope = np.polyfit([90, 100, 20, -10], [60, 70, 20, 5], 1)[0] * 1000
    assert stats.price_slope_per_gw == pytest.approx(slope)


def test_price_slope_omitted_when_scaled() -> None:
    system = frame([100, 120, 90], [10, 10, 60], [0, 10, 10])
    (stats,) = netload_by_year(system, scale_wind=2)
    assert stats.price_slope_per_gw is None


def test_stats_split_by_year() -> None:
    index = pd.date_range("2018-12-31 22:00", periods=4, freq="h", tz="UTC")
    system = pd.DataFrame(
        {"load_mw": 10.0, "wind_mw": 1.0, "solar_mw": 0.0, "price": 50.0}, index=index
    )
    assert [s.year for s in netload_by_year(system)] == [2018, 2019]


def test_missing_hours_are_excluded() -> None:
    system = frame([100, np.nan, 90], [10, 10, 10], [0, 0, 0])
    (stats,) = netload_by_year(system)
    assert stats.hours == 2


def write_opsd(path: Path, hours: int = 48) -> Path:
    index = pd.date_range("2019-01-01", periods=hours, freq="h", tz="UTC")
    hour = np.arange(hours) % 24
    pd.DataFrame(
        {
            "utc_timestamp": index.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "GB_GBN_price_day_ahead": 40 + hour,
            "GB_GBN_load_actual_entsoe_transparency": 30000 + 500 * hour,
            "GB_GBN_wind_generation_actual": 8000.0,
            "GB_GBN_solar_generation_actual": np.where((hour > 6) & (hour < 18), 4000.0, 0.0),
        }
    ).to_csv(path, index=False)
    return path


def test_load_system_aligns_columns(tmp_path: Path) -> None:
    system = load_system(OPSDCsvSource(write_opsd(tmp_path / "ts.csv")), "GB_GBN")
    assert list(system.frame.columns) == ["load_mw", "wind_mw", "solar_mw", "price"]
    assert len(system.frame) == 48
    assert system.load_flagged == 0
    one_day = load_system(
        OPSDCsvSource(tmp_path / "ts.csv"), "GB_GBN", date(2019, 1, 2), date(2019, 1, 2)
    )
    assert len(one_day.frame) == 24


def test_load_system_removes_load_glitches(tmp_path: Path) -> None:
    path = write_opsd(tmp_path / "ts.csv", hours=24 * 10)
    raw = pd.read_csv(path)
    raw.loc[100, "GB_GBN_load_actual_entsoe_transparency"] = 500.0
    raw.to_csv(path, index=False)
    system = load_system(OPSDCsvSource(path), "GB_GBN")
    assert system.load_flagged == 1
    assert np.isnan(system.frame["load_mw"].iloc[100])
    kept = load_system(OPSDCsvSource(path), "GB_GBN", clean_load=False)
    assert kept.frame["load_mw"].iloc[100] == 500.0


def test_load_system_missing_column(tmp_path: Path) -> None:
    path = tmp_path / "ts.csv"
    pd.DataFrame(
        {
            "utc_timestamp": ["2019-01-01T00:00:00Z", "2019-01-01T01:00:00Z"],
            "GB_GBN_price_day_ahead": 1.0,
        }
    ).to_csv(path, index=False)
    with pytest.raises(DataError, match="load"):
        load_system(OPSDCsvSource(path), "GB_GBN")


def test_cli_netload(tmp_path: Path) -> None:
    path = write_opsd(tmp_path / "ts.csv")
    result = CliRunner().invoke(
        app, ["netload", str(path), "--scale-wind", "4", "--must-run", "5000"]
    )
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0].startswith("net load")
    assert "wind x4" in lines[0]
    row = next(line for line in lines if line.startswith("2019"))
    assert "n/a" in row
