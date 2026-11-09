"""Tomorrow's GB day-ahead price forecast from the latest open data, and its track record.

Requires the ``openenergy[forecast]`` extra. See ``LIVE_NOTE``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from openenergy.backtest.reference import REFERENCE_BATTERY, REFERENCE_DISPATCH
from openenergy.data.fundamentals import FundamentalsSource
from openenergy.dispatch.arbitrage import optimise_dispatch
from openenergy.errors import ConfigError, DataError
from openenergy.forecast.fundamentals import FundamentalsForecaster, reference_revenue

LIVE_NOTE = (
    "OpenEnergy's fundamentals forecast, trained on every price published so far and run on "
    "the system operator's latest demand and wind forecasts for tomorrow, once a day (GitHub "
    "can start the run hours late). Ember publishes day-ahead prices two to five days late, so "
    "a live forecast knows fewer recent prices than the backtest assumes: its price level comes "
    "from the latest 24 published hours. Each forecast is scored once the day's prices are "
    "published: mean absolute error, and what a 1 MW, 2 MWh battery (GBP 5/MWh wear) earns at "
    "the real prices planning on it, against planning with perfect foresight. A day missed by "
    "a failed run is caught up later with only what was known at noon the day before and "
    "prices to three days before; it is shown but not counted in the summaries."
)
_HOUR = pd.Timedelta(hours=1)
GAS_CARRIED_DAYS = 14
COLUMNS = ["utc_timestamp", "forecast_gbp_per_mwh", "issued_utc", "catch_up"]
RECORD_FILE = "forecasts.csv"
APP_FILE = "live.json"
CATCH_UP_DAYS = 7
# A caught-up day uses the backtest's decision time and Ember's usual lag.
CATCH_UP_DECISION = pd.Timedelta(hours=12)
CATCH_UP_PRICE_LAG = pd.Timedelta(days=3)
SUMMARY_DAYS = 30
TABLE_DAYS = 14


class LatestGas(FundamentalsSource):
    """Carries the last published gas price forward: ONS publishes the daily price weekly."""

    def gas_daily(self) -> pd.Series[float]:
        gas = super().gas_daily()
        days = pd.date_range(gas.index[0], gas.index[-1] + GAS_CARRIED_DAYS * pd.Timedelta(days=1))
        return gas.reindex(days).ffill()


@dataclass(frozen=True, eq=False)
class LiveForecast:
    """One day's forecast (GBP/MWh by UTC hour) and the reference battery's plan on it.

    ``catch_up`` marks a forecast made after its day had started, for a day a run missed.
    """

    day: date
    issued: pd.Timestamp
    prices_known_until: pd.Timestamp
    prices: pd.Series[float]
    plan_mw: pd.Series[float]
    stretch: float
    catch_up: bool = False


def forecast_day(
    prices: pd.Series[float],
    source: FundamentalsSource,
    day: date,
    now: pd.Timestamp,
    catch_up: bool = False,
) -> LiveForecast:
    """Forecast ``day`` with what is known at ``now``: published prices and fundamentals.

    With ``catch_up``, only what was known at ``CATCH_UP_DECISION`` before the day and the
    prices to ``CATCH_UP_PRICE_LAG`` before it are used, so a missed day can be forecast late.
    """
    start = pd.Timestamp(day, tz="UTC")
    if catch_up:
        decision, cutoff = start - CATCH_UP_DECISION, start - CATCH_UP_PRICE_LAG
    else:
        decision, cutoff = now, start
    if decision >= start:
        raise ConfigError(f"{day} has started; a live forecast is made the day before")
    known = prices[prices.index < cutoff].dropna()
    if known.empty:
        raise DataError(f"no prices published before {day}")
    index = pd.date_range(start, periods=24, freq="h")
    source = LatestGas(source.directory)
    decisions = pd.DatetimeIndex([decision] * len(index))
    lead = (start - decision) / _HOUR
    inputs = {
        "NESO's demand forecast": source.demand(index, decisions),
        "Elexon's wind forecast": source.wind(index, decisions),
        "the gas price": source.gas(index, lag_days=2 + int(lead // 24)),
    }
    for name, values in inputs.items():
        if np.isnan(values).any():
            raise DataError(f"{name} for {day} is not published yet (run `data update`)")
    forecaster = FundamentalsForecaster(source, lead_hours=lead)
    last = pd.Timestamp(known.index.max())
    values = forecaster.forecast(known, index, known=last + _HOUR)
    plan = optimise_dispatch(
        REFERENCE_BATTERY, REFERENCE_BATTERY.initial_state(), values, 1.0, REFERENCE_DISPATCH
    )
    return LiveForecast(
        day=day,
        issued=now,
        prices_known_until=last + _HOUR,
        prices=pd.Series(values, index),
        plan_mw=pd.Series(plan.discharge_mw - plan.charge_mw, index),
        stretch=forecaster.months[start.replace(day=1)].stretch,
        catch_up=catch_up,
    )


def read_record(path: Path) -> pd.DataFrame:
    """The record of forecasts (``COLUMNS``); empty if there is none yet."""
    if not path.is_file():
        return pd.DataFrame(columns=COLUMNS)
    record = pd.read_csv(path)
    # Records written before catch-up existed hold only on-time forecasts.
    record["catch_up"] = record.get("catch_up", False)
    record["catch_up"] = record["catch_up"].fillna(False).astype(bool)
    return record[COLUMNS]


def add_forecast(record: pd.DataFrame, live: LiveForecast) -> pd.DataFrame:
    """The record with ``live`` added, replacing an earlier forecast of the same day."""
    new = pd.DataFrame(
        {
            "utc_timestamp": pd.DatetimeIndex(live.prices.index).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "forecast_gbp_per_mwh": live.prices.round(2).to_numpy(),
            "issued_utc": live.issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "catch_up": live.catch_up,
        }
    )
    kept = record[~record["utc_timestamp"].isin(new["utc_timestamp"])] if len(record) else record
    combined = pd.concat([kept, new]) if len(kept) else new
    return combined.sort_values("utc_timestamp").reset_index(drop=True)[COLUMNS]


def missing_days(record: pd.DataFrame, tomorrow: date) -> list[date]:
    """Days since the record began, up to ``CATCH_UP_DAYS`` before ``tomorrow``, with no
    forecast."""
    if record.empty:
        return []
    days = pd.DatetimeIndex(pd.to_datetime(record["utc_timestamp"], utc=True)).normalize()
    have = {d.date() for d in days}
    first = max(min(have), tomorrow - pd.Timedelta(days=CATCH_UP_DAYS))
    span = pd.date_range(first, tomorrow - pd.Timedelta(days=1), freq="D")
    return [d.date() for d in span if d.date() not in have]


def track_record(record: pd.DataFrame, actual: pd.Series[float]) -> pd.DataFrame:
    """Each forecast day with all 24 prices published: error and the reference battery.

    ``earned`` plans on the forecast and ``perfect`` on the real prices; both are paid the
    real prices. Each day starts half full, as the forecast's plan did.
    """
    columns = ["day", "mae", "earned", "perfect", "catch_up"]
    if record.empty:
        return pd.DataFrame(columns=columns)
    index = pd.DatetimeIndex(pd.to_datetime(record["utc_timestamp"], utc=True))
    frame = pd.DataFrame(
        {
            "forecast": record["forecast_gbp_per_mwh"].to_numpy(dtype=np.float64),
            "catch_up": record["catch_up"].to_numpy(dtype=bool),
        },
        index=index,
    )
    rows = []
    for day, part in frame.groupby(index.normalize()):
        hours = pd.DatetimeIndex(part.index)
        real = np.asarray(actual.reindex(hours), dtype=np.float64)
        if len(hours) != 24 or not np.isfinite(real).all():
            continue
        values = part["forecast"].to_numpy(dtype=np.float64)
        rows.append(
            {
                "day": pd.Timestamp(day).date().isoformat(),
                "mae": float(np.abs(values - real).mean()),
                "earned": reference_revenue(values, real, hours),
                "perfect": reference_revenue(real, real, hours),
                "catch_up": bool(part["catch_up"].any()),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def live_json(live: LiveForecast, track: pd.DataFrame, attribution: list[str]) -> dict[str, Any]:
    """What the web app shows: tomorrow's forecast and plan, and the track record.

    The summaries count only forecasts made before their day; caught-up days are listed.
    """
    on_time = track[~track["catch_up"].astype(bool)]
    return {
        "day": live.day.isoformat(),
        "issued": live.issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pricesKnownUntil": live.prices_known_until.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "start": live.prices.index[0].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "forecast": [round(float(v), 2) for v in live.prices],
        "planMw": [round(float(v), 3) for v in live.plan_mw],
        "stretch": live.stretch,
        "track": [
            {
                "day": str(r["day"]),
                "mae": round(float(r["mae"]), 2),
                "earned": round(float(r["earned"]), 2),
                "perfect": round(float(r["perfect"]), 2),
                "catchUp": bool(r["catch_up"]),
            }
            for r in track.tail(TABLE_DAYS).to_dict("records")
        ],
        "summary": _score(on_time.tail(SUMMARY_DAYS)),
        "sinceStart": _score(on_time)
        | {"from": str(on_time["day"].iloc[0]) if len(on_time) else None},
        "note": LIVE_NOTE,
        "attribution": attribution,
    }


def _score(rows: pd.DataFrame) -> dict[str, Any]:
    perfect = float(rows["perfect"].sum())
    return {
        "days": len(rows),
        "mae": round(float(rows["mae"].mean()), 2) if len(rows) else None,
        "capture": round(float(rows["earned"].sum()) / perfect, 3) if perfect > 0 else None,
    }


def update(
    out: Path,
    prices: pd.Series[float],
    source: FundamentalsSource,
    day: date,
    now: pd.Timestamp,
    attribution: list[str],
) -> tuple[LiveForecast, dict[str, Any], list[date]]:
    """Forecast ``day``, catch up days the record missed, score it and write the app file.

    Returns the forecast, the app file's content and the days caught up.
    """
    live = forecast_day(prices, source, day, now)
    record = add_forecast(read_record(out / RECORD_FILE), live)
    caught_up = []
    for missed in missing_days(record, day):
        try:
            record = add_forecast(record, forecast_day(prices, source, missed, now, catch_up=True))
        except DataError:
            continue
        caught_up.append(missed)
    summary = live_json(live, track_record(record, prices), attribution)
    out.mkdir(parents=True, exist_ok=True)
    record.to_csv(out / RECORD_FILE, index=False)
    (out / APP_FILE).write_text(json.dumps(summary, indent=1) + "\n")
    return live, summary, caught_up
