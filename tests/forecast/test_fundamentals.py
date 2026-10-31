from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError, DataError
from openenergy.backtest.engine import known_until
from openenergy.data import FundamentalsSource
from openenergy.forecast import PrecomputedForecast
from openenergy.forecast.fundamentals import STRETCHES, FundamentalsForecaster
from openenergy.scenario import Scenario, run_scenario

HOURS = pd.date_range("2018-01-01", "2018-09-30 23:00", freq="h", tz="UTC")
ROOT = Path(__file__).parents[2]


def synthetic(directory: Path) -> pd.Series:
    """Fundamentals and a price that depends on them, so a model has something to learn."""
    rng = np.random.default_rng(0)
    days = HOURS.normalize()
    hour = HOURS.hour.to_numpy()
    demand = 30000 + 8000 * np.sin((hour - 6) / 24 * 2 * np.pi) + rng.normal(0, 500, HOURS.size)
    wind = 6000 + 4000 * np.sin(np.arange(HOURS.size) / 97) + rng.normal(0, 300, HOURS.size)
    gas = pd.Series(30 + np.arange(days.nunique()) * 0.05, index=days.unique())
    price = 0.004 * (demand - wind) - 40 + 0.5 * gas.reindex(days - pd.Timedelta(days=2)).bfill()
    issued = (days - pd.Timedelta(days=1) + pd.Timedelta(hours=8, minutes=45)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    stamps = HOURS.strftime("%Y-%m-%dT%H:%M:%SZ")
    pd.DataFrame({"target_utc": stamps, "demand_mw": demand.round(), "issued_utc": issued}).to_csv(
        directory / "neso_demand_day_ahead.csv", index=False
    )
    pd.DataFrame({"target_utc": stamps, "wind_mw": wind.round(), "issued_utc": issued}).to_csv(
        directory / "elexon_wind_day_ahead.csv", index=False
    )
    pd.DataFrame(
        {"date": gas.index.strftime("%Y-%m-%d"), "sap_p_per_kwh": gas.to_numpy() / 10}
    ).to_csv(directory / "gas_sap_daily.csv", index=False)
    return pd.Series(np.asarray(price, dtype=np.float64), index=HOURS)


def day_of(day: str) -> pd.DatetimeIndex:
    return pd.date_range(day, periods=24, freq="h", tz="UTC")


def known(prices: pd.Series, day: pd.DatetimeIndex) -> pd.Series:
    return prices[prices.index < known_until(day[0], 12, "auction")]


def test_learns_from_fundamentals(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    forecaster = FundamentalsForecaster(FundamentalsSource(tmp_path), stretch=1.0)
    errors, naive = [], []
    for day in pd.date_range("2018-06-01", "2018-06-14", tz="UTC"):
        index = day_of(str(day.date()))
        forecast = forecaster.forecast(known(prices, index), index)
        errors.append(np.abs(forecast - prices[index]).mean())
        naive.append(np.abs(prices[index - pd.Timedelta(days=7)].to_numpy() - prices[index]).mean())
    assert np.mean(errors) < 0.5 * np.mean(naive)
    assert list(forecaster.months) == [pd.Timestamp("2018-06-01", tz="UTC")]


def test_never_uses_what_was_issued_after_the_decision(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    index = day_of("2018-06-10")
    before = FundamentalsForecaster(FundamentalsSource(tmp_path), stretch=1.0).forecast(
        known(prices, index), index
    )
    # A later wind forecast for the same day, and prices after the cutoff, change nothing.
    wind = pd.read_csv(tmp_path / "elexon_wind_day_ahead.csv")
    late = wind[wind["target_utc"].str.startswith("2018-06-10")].assign(
        wind_mw=0, issued_utc="2018-06-09T15:00:00Z"
    )
    pd.concat([wind, late]).to_csv(tmp_path / "elexon_wind_day_ahead.csv", index=False)
    after = FundamentalsForecaster(FundamentalsSource(tmp_path), stretch=1.0).forecast(
        known(prices, index), index
    )
    assert after == pytest.approx(before)
    with pytest.raises(DataError, match="history extends"):
        FundamentalsForecaster(FundamentalsSource(tmp_path)).forecast(prices, index)


def test_the_same_month_model_whatever_day_comes_first(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    index = day_of("2018-06-20")
    late_first = FundamentalsForecaster(FundamentalsSource(tmp_path), stretch=1.0)
    direct = late_first.forecast(known(prices, index), index)
    early_first = FundamentalsForecaster(FundamentalsSource(tmp_path), stretch=1.0)
    early_first.forecast(known(prices, day_of("2018-06-02")), day_of("2018-06-02"))
    assert early_first.forecast(known(prices, index), index) == pytest.approx(direct)


def test_stretch_scales_the_day_around_its_mean(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    index = day_of("2018-06-10")
    plain = FundamentalsForecaster(FundamentalsSource(tmp_path), stretch=1.0)
    double = FundamentalsForecaster(FundamentalsSource(tmp_path), stretch=2.0)
    a = plain.forecast(known(prices, index), index)
    b = double.forecast(known(prices, index), index)
    assert b.mean() == pytest.approx(a.mean())
    assert b - b.mean() == pytest.approx(2 * (a - a.mean()))
    auto = FundamentalsForecaster(FundamentalsSource(tmp_path))
    auto.forecast(known(prices, day_of("2018-09-05")), day_of("2018-09-05"))
    assert auto.months[pd.Timestamp("2018-09-01", tz="UTC")].stretch in STRETCHES


def test_needs_history_hourly_days_and_valid_settings(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    forecaster = FundamentalsForecaster(FundamentalsSource(tmp_path), stretch=1.0)
    early = day_of("2018-03-01")
    with pytest.raises(DataError, match="need 90 days"):
        forecaster.forecast(known(prices, early), early)
    half = pd.date_range("2018-06-10", periods=48, freq="30min", tz="UTC")
    with pytest.raises(ConfigError, match="hourly"):
        forecaster.forecast(known(prices, day_of("2018-06-10")), half)
    with pytest.raises(ConfigError, match="stretch"):
        FundamentalsForecaster(FundamentalsSource(tmp_path), stretch=0)
    with pytest.raises(ConfigError, match="lead_hours"):
        FundamentalsForecaster(FundamentalsSource(tmp_path), lead_hours=-1)


def test_precomputed_forecast(tmp_path: Path) -> None:
    index = day_of("2024-01-02")
    pd.DataFrame(
        {"utc_timestamp": index.strftime("%Y-%m-%dT%H:%M:%SZ"), "forecast_gbp_per_mwh": range(24)}
    ).to_csv(tmp_path / "f.csv", index=False)
    forecast = PrecomputedForecast(tmp_path / "f.csv", name="fundamentals")
    assert forecast.name == "fundamentals"
    assert forecast.forecast(pd.Series(dtype=float), index).tolist() == list(range(24))
    with pytest.raises(DataError, match="no fundamentals forecast"):
        forecast.forecast(pd.Series(dtype=float), day_of("2024-01-03"))
    pd.DataFrame({"utc_timestamp": []}).to_csv(tmp_path / "bad.csv", index=False)
    with pytest.raises(DataError, match="forecast_gbp_per_mwh"):
        PrecomputedForecast(tmp_path / "bad.csv")


def scenario(**forecast: object) -> dict[str, object]:
    return {
        "name": "f",
        "data": {"source": "ember", "path": str(ROOT / "data/prices/gb_day_ahead_ember.csv"),
                 "start": "2024-03-01", "end": "2024-03-07"},
        "battery": {"power_mw": 1, "energy_mwh": 2},
        "forecast": forecast,
    }  # fmt: skip


def test_scenario_options() -> None:
    with pytest.raises(ValueError, match="only to the fundamentals"):
        Scenario.model_validate(scenario(method="naive_last_week", path="x.csv"))
    with pytest.raises(ValueError, match="stretch"):
        Scenario.model_validate(scenario(method="fundamentals", stretch=-1.0))
    loaded = Scenario.model_validate(scenario(method="fundamentals"))
    assert loaded.information == "auction" and loaded.forecast.stretch == "auto"


def test_scenario_with_the_bundled_forecast() -> None:
    path = ROOT / "data/forecasts/gb_fundamentals_day_ahead.csv"
    if not path.is_file():
        pytest.skip("bundled fundamentals forecast not built")
    run = run_scenario(Scenario.model_validate(scenario(method="fundamentals", path=str(path))))
    assert run.summary.forecaster == "fundamentals" and run.summary.days == 7
    assert run.summary.capture_ratio is not None and run.summary.capture_ratio > 0.5
    assert date(2024, 3, 1) in run.result.daily.index
    # The bundled file is exactly what the live model forecasts.
    live = run_scenario(Scenario.model_validate(scenario(method="fundamentals")))
    assert live.result.intervals["forecast"].to_numpy() == pytest.approx(
        run.result.intervals["forecast"].to_numpy(), abs=0.006
    )
