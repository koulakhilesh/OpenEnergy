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
    "the system operator's latest demand and wind forecasts for tomorrow. Ember publishes "
    "day-ahead prices about two days late, so a live forecast knows fewer recent prices than "
    "the backtest assumes: its price level comes from the latest 24 published hours. Each "
    "forecast is scored once the day's prices are published: mean absolute error, and what a "
    "1 MW, 2 MWh battery (GBP 5/MWh wear) earns at the real prices planning on it, against "
    "planning with perfect foresight."
)
_HOUR = pd.Timedelta(hours=1)
GAS_CARRIED_DAYS = 14
COLUMNS = ["utc_timestamp", "forecast_gbp_per_mwh", "issued_utc"]
RECORD_FILE = "forecasts.csv"
APP_FILE = "live.json"


class LatestGas(FundamentalsSource):
    """Carries the last published gas price forward: ONS publishes the daily price weekly."""

    def gas_daily(self) -> pd.Series[float]:
        gas = super().gas_daily()
        days = pd.date_range(gas.index[0], gas.index[-1] + GAS_CARRIED_DAYS * pd.Timedelta(days=1))
        return gas.reindex(days).ffill()


@dataclass(frozen=True, eq=False)
class LiveForecast:
    """One day's forecast (GBP/MWh by UTC hour) and the reference battery's plan on it."""

    day: date
    issued: pd.Timestamp
    prices_known_until: pd.Timestamp
    prices: pd.Series[float]
    plan_mw: pd.Series[float]
    stretch: float


def forecast_day(
    prices: pd.Series[float], source: FundamentalsSource, day: date, now: pd.Timestamp
) -> LiveForecast:
    """Forecast ``day`` with what is known at ``now``: published prices and fundamentals."""
    start = pd.Timestamp(day, tz="UTC")
    if now >= start:
        raise ConfigError(f"{day} has started; a live forecast is made the day before")
    known = prices[prices.index < start].dropna()
    if known.empty:
        raise DataError(f"no prices published before {day}")
    index = pd.date_range(start, periods=24, freq="h")
    source = LatestGas(source.directory)
    decision = pd.DatetimeIndex([now] * len(index))
    lead = (start - now) / _HOUR
    inputs = {
        "NESO's demand forecast": source.demand(index, decision),
        "Elexon's wind forecast": source.wind(index, decision),
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
    )


def add_forecast(record: pd.DataFrame, live: LiveForecast) -> pd.DataFrame:
    """The record of forecasts (``COLUMNS``) with ``live`` added, replacing an earlier run."""
    new = pd.DataFrame(
        {
            "utc_timestamp": pd.DatetimeIndex(live.prices.index).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "forecast_gbp_per_mwh": live.prices.round(2).to_numpy(),
            "issued_utc": live.issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    kept = record[~record["utc_timestamp"].isin(new["utc_timestamp"])] if len(record) else record
    combined = pd.concat([kept, new]) if len(kept) else new
    return combined.sort_values("utc_timestamp").reset_index(drop=True)[COLUMNS]


def track_record(record: pd.DataFrame, actual: pd.Series[float]) -> pd.DataFrame:
    """Each forecast day with all 24 prices published: error and the reference battery.

    ``earned`` plans on the forecast and ``perfect`` on the real prices; both are paid the
    real prices. Each day starts half full, as the forecast's plan did.
    """
    columns = ["day", "mae", "earned", "perfect"]
    if record.empty:
        return pd.DataFrame(columns=columns)
    forecast = pd.Series(
        record["forecast_gbp_per_mwh"].to_numpy(dtype=np.float64),
        pd.DatetimeIndex(pd.to_datetime(record["utc_timestamp"], utc=True)),
    )
    rows = []
    for day, part in forecast.groupby(pd.DatetimeIndex(forecast.index).normalize()):
        index = pd.DatetimeIndex(part.index)
        real = np.asarray(actual.reindex(index), dtype=np.float64)
        if len(index) != 24 or not np.isfinite(real).all():
            continue
        values = part.to_numpy(dtype=np.float64)
        rows.append(
            {
                "day": pd.Timestamp(day).date().isoformat(),
                "mae": float(np.abs(values - real).mean()),
                "earned": reference_revenue(values, real, index),
                "perfect": reference_revenue(real, real, index),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def live_json(
    live: LiveForecast, track: pd.DataFrame, attribution: list[str], days: int = 90
) -> dict[str, Any]:
    """What the web app shows: tomorrow's forecast and plan, and the recent track record."""
    recent = track.tail(days)
    perfect = float(recent["perfect"].sum())
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
                "day": str(day),
                "mae": round(float(mae), 2),
                "earned": round(float(earned), 2),
                "perfect": round(float(best), 2),
            }
            for day, mae, earned, best in zip(
                recent["day"], recent["mae"], recent["earned"], recent["perfect"], strict=True
            )
        ],
        "summary": {
            "days": len(recent),
            "mae": round(float(recent["mae"].mean()), 2) if len(recent) else None,
            "capture": round(float(recent["earned"].sum()) / perfect, 3) if perfect > 0 else None,
        },
        "note": LIVE_NOTE,
        "attribution": attribution,
    }


def update(
    out: Path,
    prices: pd.Series[float],
    source: FundamentalsSource,
    day: date,
    now: pd.Timestamp,
    attribution: list[str],
) -> tuple[LiveForecast, dict[str, Any]]:
    """Forecast ``day``, add it to ``out``'s record, score the record and write the app file."""
    live = forecast_day(prices, source, day, now)
    record_file = out / RECORD_FILE
    record = pd.read_csv(record_file) if record_file.is_file() else pd.DataFrame(columns=COLUMNS)
    record = add_forecast(record, live)
    summary = live_json(live, track_record(record, prices), attribution)
    out.mkdir(parents=True, exist_ok=True)
    record.to_csv(record_file, index=False)
    (out / APP_FILE).write_text(json.dumps(summary, indent=1) + "\n")
    return live, summary
