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
    CATCH_UP_DAYS,
    COLUMNS,
    RECORD_FILE,
    SUMMARY_DAYS,
    TABLE_DAYS,
    LatestGas,
    add_forecast,
    forecast_day,
    live_json,
    missing_days,
    read_record,
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


def test_a_missed_day_is_caught_up_with_only_what_was_known_the_day_before(
    tmp_path: Path,
) -> None:
    prices = synthetic(tmp_path)
    source = FundamentalsSource(tmp_path)
    day, late = date(2018, 6, 10), pd.Timestamp("2018-06-12T16:00Z")
    caught = forecast_day(prices, source, day, late, catch_up=True)
    assert caught.catch_up and caught.issued == late
    assert caught.prices_known_until == pd.Timestamp("2018-06-07", tz="UTC")
    # Prices published since change nothing.
    early = prices[prices.index < pd.Timestamp("2018-06-07", tz="UTC")]
    again = forecast_day(early, source, day, late, catch_up=True)
    assert again.prices.to_numpy() == pytest.approx(caught.prices.to_numpy())
    with pytest.raises(ConfigError, match="has started"):
        forecast_day(prices, source, day, late)


def test_update_catches_up_missed_days_but_does_not_count_them(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    out = tmp_path / "live"
    source = FundamentalsSource(tmp_path)
    first = pd.Timestamp("2018-06-09T16:00Z")
    update(out, prices[prices.index < first], source, date(2018, 6, 10), first, ["x"])
    # Runs for 11 and 12 June were missed; the next one comes on the 12th.
    later = pd.Timestamp("2018-06-12T16:00Z")
    _, summary, caught_up = update(
        out, prices[prices.index < later], source, date(2018, 6, 13), later, ["x"]
    )
    assert caught_up == [date(2018, 6, 11), date(2018, 6, 12)]
    record = read_record(out / RECORD_FILE)
    assert len(record) == 4 * 24
    assert record.groupby(record["utc_timestamp"].str[:10])["catch_up"].first().to_dict() == {
        "2018-06-10": False,
        "2018-06-11": True,
        "2018-06-12": True,
        "2018-06-13": False,
    }
    assert [(r["day"], r["catchUp"]) for r in summary["track"]] == [
        ("2018-06-10", False),
        ("2018-06-11", True),
    ]
    assert summary["summary"]["days"] == summary["sinceStart"]["days"] == 1
    assert summary["sinceStart"]["from"] == "2018-06-10"
    assert summary["waiting"] == ["2018-06-12"]
    assert summary["pricesPublishedUntil"] == "2018-06-12T16:00:00Z"


def test_missing_days_start_with_the_record_and_look_back_a_week() -> None:
    def record_of(*days: str) -> pd.DataFrame:
        stamps = [f"{d}T{h:02d}:00:00Z" for d in days for h in range(24)]
        return pd.DataFrame({"utc_timestamp": stamps})

    assert missing_days(pd.DataFrame(columns=COLUMNS), date(2018, 6, 13)) == []
    assert missing_days(record_of("2018-06-10", "2018-06-12"), date(2018, 6, 13)) == [
        date(2018, 6, 11)
    ]
    long_ago = missing_days(record_of("2018-05-01"), date(2018, 6, 13))
    assert long_ago[0] == date(2018, 6, 13) - pd.Timedelta(days=CATCH_UP_DAYS)
    assert long_ago[-1] == date(2018, 6, 12)


def test_summaries_cover_the_last_30_days_and_since_the_start(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    live = forecast_day(
        prices, FundamentalsSource(tmp_path), date(2018, 9, 20), NOW.replace(month=9, day=19)
    )
    days = pd.date_range("2018-07-01", periods=40, freq="D")
    track = pd.DataFrame(
        {
            "day": days.strftime("%Y-%m-%d"),
            "mae": np.arange(40, dtype=float),
            "earned": 1.0,
            "perfect": 2.0,
            "catch_up": [i == 39 for i in range(40)],
        }
    )
    summary = live_json(live, track, [])
    assert summary["summary"]["days"] == SUMMARY_DAYS
    assert summary["summary"]["mae"] == pytest.approx(np.arange(9, 39).mean())
    assert summary["sinceStart"] == {"days": 39, "mae": 19.0, "capture": 0.5, "from": "2018-07-01"}
    assert len(summary["track"]) == TABLE_DAYS and summary["track"][-1]["catchUp"]


def test_old_records_without_catch_up_read_as_on_time(tmp_path: Path) -> None:
    path = tmp_path / RECORD_FILE
    pd.DataFrame(
        {
            "utc_timestamp": ["2018-06-10T00:00:00Z"],
            "forecast_gbp_per_mwh": [50.0],
            "issued_utc": ["x"],
        }
    ).to_csv(path, index=False)
    record = read_record(path)
    assert list(record.columns) == COLUMNS and not record["catch_up"].any()


def test_a_rerun_keeps_the_first_forecast_unless_asked_to_replace_it(tmp_path: Path) -> None:
    prices = synthetic(tmp_path)
    out = tmp_path / "live"
    source = FundamentalsSource(tmp_path)
    day = date(2018, 6, 10)
    first, later = pd.Timestamp("2018-06-09T09:30Z"), pd.Timestamp("2018-06-09T20:00Z")
    made, _, _ = update(out, prices[prices.index < first], source, day, first, ["x"])
    record = (out / RECORD_FILE).read_text()
    app_file = json.loads((out / APP_FILE).read_text())

    kept, _, _ = update(out, prices[prices.index < later], source, day, later, ["x"])
    assert kept.issued == first
    assert kept.prices.to_numpy() == pytest.approx(made.prices.round(2).to_numpy())
    assert kept.plan_mw.to_numpy() == pytest.approx(made.plan_mw.to_numpy(), abs=1e-3)
    assert (out / RECORD_FILE).read_text() == record
    again = json.loads((out / APP_FILE).read_text())
    for key in ("issued", "pricesKnownUntil", "forecast", "planMw"):
        assert again[key] == app_file[key]

    redone, _, _ = update(
        out, prices[prices.index < later], source, day, later, ["x"], replace=True
    )
    assert redone.issued == later
    assert read_record(out / RECORD_FILE)["issued_utc"].unique().tolist() == [
        "2018-06-09T20:00:00Z"
    ]
