from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError, InfeasibleDispatchError
from openenergy.assets import BatterySpec
from openenergy.backtest import BacktestConfig, Carbon, Site, run_backtest
from openenergy.data import PriceSeries
from openenergy.dispatch import DispatchConfig, GridConnection
from openenergy.forecast import PerfectForesight
from openenergy.metrics import summarise
from openenergy.scenario import load_scenario, run_scenario, write_outputs


def flat_prices(days: int = 3, price: float = 50.0) -> PriceSeries:
    index = pd.date_range("2019-01-01", periods=days * 24, freq="h", tz="UTC")
    return PriceSeries(pd.Series(price, index=index), "GBP", "GB")


def clean_early(index: pd.DatetimeIndex, low_hours: range = range(0, 6)) -> pd.Series:
    hour = np.asarray(index.hour)
    return pd.Series(np.where(np.isin(hour, list(low_hours)), 100.0, 300.0), index=index)


def lossy(**overrides: float) -> BatterySpec:
    params: dict[str, float] = {
        "power_mw": 1,
        "energy_mwh": 2,
        "eta_charge": 0.95,
        "eta_discharge": 0.95,
        "initial_soc": 0,
    }
    params.update(overrides)
    return BatterySpec(**params)


def test_carbon_price_shifts_charging_to_clean_hours() -> None:
    prices = flat_prices()
    ci = clean_early(prices.prices.index)
    carbon = Carbon(ci, 50.0, planning="actual")
    result = run_backtest(lossy(), prices, PerfectForesight(prices), carbon=carbon)
    day = result.intervals.iloc[:24]
    clean = np.asarray(day.index.hour) < 6
    assert day["charge_mw"][clean].sum() > 0
    assert day["charge_mw"][~clean].sum() == pytest.approx(0.0)
    # Flat market price, so the battery loses a little money but avoids net emissions.
    assert result.daily["revenue"].iloc[0] < 0
    assert result.daily["emissions_t"].iloc[0] < 0
    assert result.daily["expected_revenue"].iloc[0] < 0


def test_without_carbon_price_dispatch_ignores_intensity() -> None:
    prices = flat_prices()
    ci = clean_early(prices.prices.index)
    result = run_backtest(lossy(), prices, PerfectForesight(prices), carbon=Carbon(ci))
    assert result.intervals["charge_mw"].sum() == 0.0
    assert result.daily["emissions_t"].sum() == 0.0
    assert "intensity" in result.intervals.columns


def test_last_week_planning_follows_last_weeks_pattern() -> None:
    prices = flat_prices(days=9)
    index = prices.prices.index
    first_week = index < pd.Timestamp("2019-01-08", tz="UTC")
    ci = pd.Series(
        np.where(first_week, clean_early(index), clean_early(index, range(12, 18))), index=index
    )
    result = run_backtest(lossy(), prices, PerfectForesight(prices), carbon=Carbon(ci, 50.0))
    assert sorted(result.skipped)[0] == pd.Timestamp("2019-01-01").date()
    day8 = result.intervals.loc["2019-01-08"]
    charged_hours = set(day8.index.hour[day8["charge_mw"] > 0])
    assert charged_hours and charged_hours <= set(range(0, 6))


def test_last_week_planning_never_sees_after_decision_time() -> None:
    prices = flat_prices(days=9)
    ci = clean_early(prices.prices.index)
    base = run_backtest(lossy(), prices, PerfectForesight(prices), carbon=Carbon(ci, 50.0))
    changed = ci.copy()
    changed.loc["2019-01-08"] = 100.0
    other = run_backtest(lossy(), prices, PerfectForesight(prices), carbon=Carbon(changed, 50.0))
    assert other.intervals.loc["2019-01-08", "charge_mw"].tolist() == pytest.approx(
        base.intervals.loc["2019-01-08", "charge_mw"].tolist()
    )


def test_missing_intensity_skips_day() -> None:
    prices = flat_prices()
    ci = clean_early(prices.prices.index)
    ci.iloc[30] = np.nan
    result = run_backtest(lossy(), prices, PerfectForesight(prices), carbon=Carbon(ci))
    assert pd.Timestamp("2019-01-02").date() in result.skipped
    assert "carbon" in next(iter(result.skipped.values()))


def test_site_emissions_count_plant_export() -> None:
    prices = flat_prices(days=1)
    index = prices.prices.index
    site = Site(pd.Series(2.0, index=index), GridConnection(5.0))
    ci = pd.Series(250.0, index=index)
    result = run_backtest(lossy(), prices, PerfectForesight(prices), site=site, carbon=Carbon(ci))
    assert result.daily["emissions_t"].iloc[0] == pytest.approx(-2 * 24 * 250 / 1000)
    assert summarise(result).emissions_t == pytest.approx(-12.0)


def test_summary_without_carbon_has_no_emissions() -> None:
    prices = flat_prices(days=1)
    assert summarise(run_backtest(lossy(), prices, PerfectForesight(prices))).emissions_t is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"price_per_t": -1.0}, "price_per_t"), ({"planning": "forecast"}, "planning")],
)
def test_carbon_validation(kwargs: dict[str, object], message: str) -> None:
    index = pd.date_range("2019-01-01", periods=2, freq="h", tz="UTC")
    with pytest.raises(ConfigError, match=message):
        Carbon(pd.Series(1.0, index=index), **kwargs)  # type: ignore[arg-type]


def test_infeasible_still_reports_day() -> None:
    prices = flat_prices(days=1)
    ci = clean_early(prices.prices.index)
    spec = BatterySpec(power_mw=0.01, energy_mwh=2, initial_soc=0)
    config = BacktestConfig(dispatch=DispatchConfig(end_soc=1.0))
    carbon = Carbon(ci, 10.0, planning="actual")
    with pytest.raises(InfeasibleDispatchError, match="2019-01-01"):
        run_backtest(spec, prices, PerfectForesight(prices), config, carbon=carbon)


def write_carbon(path: Path, days: int) -> Path:
    index = pd.date_range("2019-01-01", periods=days * 48, freq="30min", tz="UTC")
    hour = np.asarray(index.hour)
    values = np.where(hour < 6, 120.0, 280.0)
    pd.DataFrame(
        {
            "utc_timestamp": index.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "forecast": values,
            "actual": values,
        }
    ).to_csv(path, index=False)
    return path


def test_scenario_with_carbon(tmp_path: Path, opsd_csv: Path) -> None:
    carbon = write_carbon(tmp_path / "ci.csv", 21)
    path = tmp_path / "carbon.yaml"
    path.write_text(
        f"name: carbon-test\ndata: {{path: {opsd_csv}, start: 2019-01-08}}\n"
        "battery: {power_mw: 1, energy_mwh: 2}\nforecast: perfect_foresight\n"
        f"carbon: {{path: {carbon}, price_per_t: 80}}\n"
    )
    run = run_scenario(load_scenario(path))
    assert run.summary.emissions_t is not None
    assert run.summary.days == 14
    out = write_outputs(run, tmp_path / "out")
    payload = (out / "summary.json").read_text()
    assert "National Energy System Operator" in payload
    assert "average" in payload
    assert "last_week" in payload


@pytest.mark.parametrize(
    ("carbon", "message"),
    [
        ("{path: ci.csv, price_per_t: -5}", "price_per_t"),
        ("{path: ci.csv, planning: forecast}", "planning"),
    ],
)
def test_scenario_carbon_validation(
    tmp_path: Path, opsd_csv: Path, carbon: str, message: str
) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        f"name: x\ndata: {{path: {opsd_csv}}}\nbattery: {{power_mw: 1, energy_mwh: 2}}\n"
        f"carbon: {carbon}\n"
    )
    with pytest.raises(ConfigError, match=message):
        load_scenario(path)
