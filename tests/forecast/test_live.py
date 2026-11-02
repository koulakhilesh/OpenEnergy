import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from openenergy import ConfigError, DataError
from openenergy.cli import app
from openenergy.data import FundamentalsSource
from openenergy.forecast.live import (
    APP_FILE,
    COLUMNS,
    RECORD_FILE,
    LatestGas,
    add_forecast,
    forecast_day,
    live_json,
    track_record,
    update,
)

from .test_fundamentals import synthetic

NOW = pd.Timestamp("2018-06-09T09:30:00Z")


def test_forecasts_tomorrow_from_prices_that_end_days_earlier(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    lagging = prices[prices.index < pd.Timestamp("2018-06-07", tz="UTC")]
    live = forecast_day(lagging, FundamentalsSource(tmp_path), date(2018, 6, 10), NOW)
    real = prices[live.prices.index]
    naive = prices[live.prices.index - pd.Timedelta(days=7)].to_numpy()
    assert len(live.prices) == 24
    assert live.prices_known_until == pd.Timestamp("2018-06-07", tz="UTC")
    assert np.abs(live.prices.to_numpy() - real).mean() < np.abs(naive - real).mean()
    assert live.plan_mw.abs().max() <= 1.0 + 1e-9
    assert live.plan_mw[live.prices.idxmax()] > 0 > live.plan_mw[live.prices.idxmin()]


def test_refuses_a_day_that_started_or_has_no_fundamentals(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    source = FundamentalsSource(tmp_path)
    with pytest.raises(ConfigError, match="has started"):
        forecast_day(prices, source, date(2018, 6, 9), NOW)
    with pytest.raises(DataError, match="demand forecast for 2018-10-02"):
        forecast_day(prices, source, date(2018, 10, 2), pd.Timestamp("2018-10-01T09:30Z"))


def test_carries_the_last_gas_price_forward(tmp_path: Path) -> None:
    synthetic(tmp_path)
    gas = pd.read_csv(tmp_path / "gas_sap_daily.csv")
    gas[gas["date"] < "2018-06-05"].to_csv(tmp_path / "gas_sap_daily.csv", index=False)
    carried = LatestGas(tmp_path).gas_daily()
    assert (
        carried[pd.Timestamp("2018-06-12", tz="UTC")]
        == carried[pd.Timestamp("2018-06-04", tz="UTC")]
    )
    assert carried.index[-1] == pd.Timestamp("2018-06-18", tz="UTC")


def test_record_replaces_a_rerun_and_scores_published_days(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    source = FundamentalsSource(tmp_path)
    record = pd.DataFrame(columns=COLUMNS)
    for day in (date(2018, 6, 10), date(2018, 6, 11)):
        now = pd.Timestamp(day, tz="UTC") - pd.Timedelta(hours=14)
        live = forecast_day(prices[prices.index < now - pd.Timedelta(days=2)], source, day, now)
        record = add_forecast(record, live)
    record = add_forecast(record, live)
    assert len(record) == 48
    track = track_record(record, prices[prices.index < pd.Timestamp("2018-06-11T12:00Z")])
    assert list(track["day"]) == ["2018-06-10"]
    row = track.iloc[0]
    assert 0 < row["earned"] <= row["perfect"]
    summary = live_json(live, track, ["source"])
    assert summary["day"] == "2018-06-11"
    assert summary["summary"]["days"] == 1
    assert summary["summary"]["capture"] == pytest.approx(row["earned"] / row["perfect"], abs=1e-3)
    assert len(summary["forecast"]) == len(summary["planMw"]) == 24


def test_update_keeps_the_record_and_writes_the_app_file(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    out = tmp_path / "live"
    for day in (date(2018, 6, 10), date(2018, 6, 11)):
        now = pd.Timestamp(day, tz="UTC") - pd.Timedelta(hours=14)
        update(out, prices[prices.index < now], FundamentalsSource(tmp_path), day, now, ["x"])
    record = pd.read_csv(out / RECORD_FILE)
    assert len(record) == 48 and list(record.columns) == COLUMNS
    app_file = json.loads((out / APP_FILE).read_text())
    assert app_file["day"] == "2018-06-11" and app_file["attribution"] == ["x"]


def test_cli_writes_the_record_and_the_app_file(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    eur = prices[prices.index < pd.Timestamp("2018-06-07", tz="UTC")]
    pd.DataFrame(
        {"utc_timestamp": eur.index.strftime("%Y-%m-%dT%H:%M:%SZ"), "price_eur_per_mwh": eur}
    ).to_csv(tmp_path / "gb_day_ahead_ember.csv", index=False)
    pd.DataFrame({"date": ["2018-01-01"], "gbp_per_eur": [1.0]}).to_csv(
        tmp_path / "ecb_gbp_per_eur.csv", index=False
    )
    out = tmp_path / "live"
    result = CliRunner().invoke(
        app,
        [
            "forecast", "live", "--out", str(out), "--day", "2099-01-01",
            "--prices", str(tmp_path / "gb_day_ahead_ember.csv"), "--fundamentals", str(tmp_path),
        ],
    )  # fmt: skip
    assert result.exit_code == 1
    assert "not published yet" in result.output
    assert not out.exists()
