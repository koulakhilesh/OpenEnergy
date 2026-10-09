from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from openenergy import ConfigError, DataError
from openenergy.forecast.ml import GradientBoostingForecaster, make_features
from openenergy.scenario import load_scenario, run_scenario

HOUR = pd.Timedelta(hours=1)


def synthetic(days: int, seed: int = 0) -> pd.Series:
    index = pd.date_range("2019-01-01", periods=days * 24, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    hour = np.arange(index.size) % 24
    weekend = (index.dayofweek >= 5).astype(float)
    values = 40 + 20 * np.sin(hour * 2 * np.pi / 24) - 8 * weekend + rng.normal(0, 1, index.size)
    return pd.Series(values, index=index)


def day(start: str) -> pd.DatetimeIndex:
    return pd.date_range(start, periods=24, freq="h", tz="UTC")


def test_features_hide_lags_after_decision_time() -> None:
    prices = synthetic(30)
    target = day("2019-01-20")
    features = make_features(target, prices, lead_hours=12)
    lag_1d = features["lag_1d"].to_numpy()
    assert not np.isnan(lag_1d[:12]).any()
    assert np.isnan(lag_1d[12:]).all()
    assert not features[["lag_2d", "lag_7d", "lag_14d"]].isna().any().any()
    assert features["lag_7d"].iloc[5] == prices[target[5] - 7 * 24 * HOUR]


def test_features_calendar_columns() -> None:
    features = make_features(day("2019-01-05"), synthetic(10), lead_hours=12)
    assert features["hour"].tolist() == list(range(24))
    assert (features["weekend"] == 1).all()


def test_forecast_ignores_history_after_decision_time() -> None:
    prices = synthetic(60)
    model = GradientBoostingForecaster(lead_hours=12).fit(
        prices[: pd.Timestamp("2019-02-01", tz="UTC")]
    )
    target = day("2019-02-20")
    cutoff = target[0] - 12 * HOUR
    honest = model.forecast(prices[prices.index < cutoff], target)
    leaky = model.forecast(prices, target)
    assert honest.tolist() == leaky.tolist()


def test_forecast_learns_daily_and_weekly_shape() -> None:
    prices = synthetic(120)
    split = pd.Timestamp("2019-03-15", tz="UTC")
    model = GradientBoostingForecaster().fit(prices[prices.index < split])
    errors = []
    for start in pd.date_range("2019-03-20", "2019-04-25", freq="D", tz="UTC"):
        target = day(str(start.date()))
        history = prices[prices.index < target[0] - 12 * HOUR]
        errors.append(model.forecast(history, target) - prices.loc[target].to_numpy())
    assert np.abs(np.concatenate(errors)).mean() < 2.0


def test_forecast_inside_training_window_is_rejected() -> None:
    prices = synthetic(40)
    model = GradientBoostingForecaster().fit(prices)
    with pytest.raises(DataError, match="training"):
        model.forecast(prices, day("2019-01-30"))


def test_unfitted_model_raises() -> None:
    with pytest.raises(ConfigError, match="fit"):
        GradientBoostingForecaster().forecast(synthetic(20), day("2019-01-25"))


def test_fit_needs_enough_data() -> None:
    with pytest.raises(DataError, match="training"):
        GradientBoostingForecaster().fit(synthetic(1).iloc[:5])


def write_csv(path: Path, prices: pd.Series) -> Path:
    pd.DataFrame(
        {
            "utc_timestamp": prices.index.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "GB_GBN_price_day_ahead": prices.to_numpy(),
        }
    ).to_csv(path, index=False)
    return path


def test_scenario_trains_before_backtest(tmp_path: Path) -> None:
    csv = write_csv(tmp_path / "p.csv", synthetic(90))
    path = tmp_path / "gb.yaml"
    path.write_text(
        f"name: gb-ml\ndata: {{path: {csv}, start: 2019-03-01, end: 2019-03-14}}\n"
        "battery: {power_mw: 1, energy_mwh: 2}\n"
        "forecast: {method: gradient_boosting, train_start: 2019-01-01, train_end: 2019-02-28}\n"
    )
    run = run_scenario(load_scenario(path))
    assert run.summary.forecaster == "gradient_boosting"
    assert run.summary.days == 14
    assert run.summary.capture_ratio is not None
    assert run.summary.capture_ratio > 0.8


@pytest.mark.parametrize(
    ("forecast", "data_start", "message"),
    [
        ("{method: gradient_boosting}", "2019-03-01", "train_end"),
        ("{method: gradient_boosting, train_end: 2019-03-01}", "2019-03-01", "before"),
        ("{method: gradient_boosting, train_end: 2019-02-01}", None, "data.start"),
    ],
)
def test_scenario_validates_training_window(
    tmp_path: Path, forecast: str, data_start: str | None, message: str
) -> None:
    start = f", start: {data_start}" if data_start else ""
    path = tmp_path / "bad.yaml"
    path.write_text(
        f"name: x\ndata: {{path: a.csv{start}}}\nbattery: {{power_mw: 1, energy_mwh: 1}}\n"
        f"forecast: {forecast}\n"
    )
    with pytest.raises(ConfigError, match=message):
        load_scenario(path)


def test_training_window_dates_are_parsed(tmp_path: Path) -> None:
    path = tmp_path / "ok.yaml"
    path.write_text(
        "name: x\ndata: {path: a.csv, start: 2019-03-01}\nbattery: {power_mw: 1, energy_mwh: 1}\n"
        "forecast: {method: gradient_boosting, train_start: 2018-01-01, train_end: 2019-02-28}\n"
    )
    scenario = load_scenario(path)
    assert scenario.forecast.train_start == date(2018, 1, 1)
    assert scenario.forecast.train_end == date(2019, 2, 28)
