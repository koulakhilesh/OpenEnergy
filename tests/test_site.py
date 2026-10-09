from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from openenergy import ConfigError, DataError
from openenergy.assets import BatterySpec
from openenergy.backtest import Site, run_backtest, run_plant_backtest
from openenergy.cli import app
from openenergy.data import PriceSeries
from openenergy.dispatch import GridConnection
from openenergy.forecast import PerfectForesight
from openenergy.metrics import summarise
from openenergy.scenario import load_scenario, run_scenario, write_outputs


def prices(days: int = 5) -> PriceSeries:
    index = pd.date_range("2019-01-01", periods=days * 24, freq="h", tz="UTC")
    hour = np.arange(index.size) % 24
    return PriceSeries(pd.Series(np.where(hour < 12, 10.0, 50.0), index=index), "GBP", "GB")


def site(series: PriceSeries, limit: float, premium: float = 0.0) -> Site:
    index = series.prices.index
    hour = np.asarray(index.hour)
    output = pd.Series(np.where((hour >= 6) & (hour < 12), 2.0, 0.0), index=index)
    return Site(output, GridConnection(limit, premium_per_mwh=premium))


def test_site_backtest_recaptures_clipping() -> None:
    series = prices()
    battery = BatterySpec(power_mw=1, energy_mwh=4, eta_charge=1, eta_discharge=1, initial_soc=0)
    result = run_backtest(battery, series, PerfectForesight(series), site=site(series, 1.0))
    daily = result.daily
    assert list(daily.columns)[:4] == ["revenue", "premium", "expected_revenue", "available_mwh"]
    assert daily["available_mwh"].iloc[0] == pytest.approx(12.0)
    # 6 MWh exported at 10, 4 MWh stored and sold at 50, 2 MWh curtailed (battery full).
    assert daily["curtailed_mwh"].iloc[0] == pytest.approx(2.0)
    assert daily["revenue"].iloc[0] == pytest.approx(6 * 10 + 4 * 50)
    frame = result.intervals
    assert (frame["export_mw"] <= 1.0 + 1e-6).all()
    split = frame["plant_to_grid_mw"] + frame["plant_to_battery_mw"] + frame["curtailed_mw"]
    assert split.to_numpy() == pytest.approx(frame["available_mw"].to_numpy())


def test_site_summary_reports_plant_fields() -> None:
    series = prices()
    battery = BatterySpec(power_mw=1, energy_mwh=4)
    result = run_backtest(battery, series, PerfectForesight(series), site=site(series, 1.0, 5.0))
    summary = summarise(result, benchmark=result)
    assert summary.revenue_per_mw_year is None
    assert summary.captured_spread is None
    assert summary.premium == pytest.approx(float(result.daily["premium"].sum()))
    assert summary.total == pytest.approx(summary.revenue + summary.premium)
    assert summary.capture_ratio == pytest.approx(1.0)


def test_plant_backtest_clips_at_own_limit() -> None:
    series = prices(days=3)
    result = run_plant_backtest(site(series, 1.5), series, PerfectForesight(series))
    assert result.daily["curtailed_mwh"].tolist() == pytest.approx([3.0, 3.0, 3.0])
    assert result.daily["revenue"].tolist() == pytest.approx([90.0, 90.0, 90.0])


def test_missing_plant_output_skips_day() -> None:
    series = prices(days=3)
    gappy = site(series, 1.0)
    gappy.available_mw.iloc[30] = np.nan
    result = run_backtest(BatterySpec(1, 2), series, PerfectForesight(series), site=gappy)
    assert date(2019, 1, 2) in result.skipped
    assert "plant output" in result.skipped[date(2019, 1, 2)]


def test_negative_plant_output_rejected() -> None:
    series = prices(days=2)
    bad = site(series, 1.0)
    bad.available_mw.iloc[3] = -1.0
    with pytest.raises(DataError, match="non-negative"):
        run_backtest(BatterySpec(1, 2), series, PerfectForesight(series), site=bad)


def write_scenario(tmp_path: Path, csv: Path, extra: str) -> Path:
    path = tmp_path / "site.yaml"
    path.write_text(
        f"name: site-test\ndata: {{path: {csv}, start: 2019-01-08}}\n"
        "battery: {power_mw: 2, energy_mwh: 4}\nforecast: naive_last_week\n" + extra
    )
    return path


def test_scenario_grid_defaults_to_plant_capacity(tmp_path: Path, site_csv: Path) -> None:
    scenario = load_scenario(
        write_scenario(
            tmp_path, site_csv, "assets: {pv: {capacity_mw: 5}, wind: {capacity_mw: 3}}\n"
        )
    )
    grid = scenario.connection()
    assert grid is not None
    assert grid.export_limit_mw == 8.0
    assert grid.import_limit_mw == 8.0
    assert [p.technology for p in scenario.assets.plants()] == ["solar", "wind"]  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ("grid: {export_limit_mw: 5}\n", "assets"),
        ("assets: {}\n", "pv or wind"),
        ("assets: {pv: {capacity_mw: 0}}\n", "capacity_mw"),
        ("assets: {pv: {capacity_mw: 5}}\ngrid: {export_limit_mw: -1}\n", "export_limit_mw"),
    ],
)
def test_scenario_site_validation(tmp_path: Path, site_csv: Path, extra: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_scenario(write_scenario(tmp_path, site_csv, extra))


def test_scenario_runs_site_with_comparisons(tmp_path: Path, site_csv: Path) -> None:
    path = write_scenario(
        tmp_path,
        site_csv,
        "assets: {pv: {capacity_mw: 5}}\ngrid: {export_limit_mw: 4, premium_per_mwh: 10}\n",
    )
    run = run_scenario(load_scenario(path))
    assert run.summary.days == 14
    assert run.summary.premium is not None and run.summary.premium > 0
    assert run.colocation is not None
    assert run.colocation.plant_alone > 0
    assert run.colocation.value == pytest.approx(
        run.colocation.colocated - run.colocation.plant_alone - run.colocation.battery_alone
    )
    assert run.plant_capture is not None
    assert run.plant_capture.capture_rate is not None and run.plant_capture.capture_rate > 1

    out = write_outputs(run, tmp_path / "out")
    payload = (out / "summary.json").read_text()
    assert '"colocation"' in payload
    assert "upper bound" in payload
    assert "plant_to_battery_mw" in (out / "intervals.csv").read_text().splitlines()[0]


def test_battery_only_scenarios_are_unchanged(scenario_file: Path) -> None:
    run = run_scenario(load_scenario(scenario_file))
    assert run.colocation is None
    assert run.summary.revenue_per_mw_year is not None
    assert "premium" not in run.result.daily.columns


def test_cli_run_site(tmp_path: Path, site_csv: Path) -> None:
    path = write_scenario(tmp_path, site_csv, "assets: {pv: {capacity_mw: 5}}\n")
    result = CliRunner().invoke(app, ["run", str(path), "--out", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    assert "co-location value" in result.output
    assert "plant captured price" in result.output
    assert "revenue per MW-year" not in result.output
