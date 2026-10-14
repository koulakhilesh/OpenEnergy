"""Results for the app: a compact per-MW summary and daily revenue, precomputed or live."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import pandas as pd

from openenergy.app.runs import (
    HISTORY_YEARS,
    RESPONSE_FROM,
    SCENARIO_YEARS,
    Request,
    run,
)
from openenergy.data.fes import PATHWAYS
from openenergy.errors import DataError
from openenergy.metrics.summary import DAYS_PER_YEAR
from openenergy.report.load import BatteryOutput

PRECOMPUTED_HOURS = (1.0, 2.0, 4.0)
SUMMARY_FILE = "app/summary.csv"
DAILY_FILE = "app/daily.csv"


@dataclass(frozen=True, eq=False)
class Result:
    """One request's per-MW results; ``daily`` has ``revenue`` and ``benchmark_revenue``."""

    request: Request
    summary: dict[str, float]
    daily: pd.DataFrame
    precomputed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.request.key,
            "label": self.request.label,
            "precomputed": self.precomputed,
            "summary": self.summary,
            "daily": {
                "date": list(self.daily.index),
                "revenue": self.daily["revenue"].round(2).tolist(),
                "benchmark_revenue": self.daily["benchmark_revenue"].round(2).tolist(),
            },
        }


def grid() -> Iterator[Request]:
    """Every request the app precomputes."""
    for hours in PRECOMPUTED_HOURS:
        for forecast in ("naive_last_week", "perfect_foresight"):
            for year in range(HISTORY_YEARS[0], HISTORY_YEARS[1] + 1):
                yield Request("history", year, hours, forecast)
                if year >= RESPONSE_FROM:
                    yield Request("history", year, hours, forecast, "dc")
                    yield Request("history", year, hours, forecast, "dc_dm")
            for pathway in PATHWAYS:
                for target in SCENARIO_YEARS:
                    yield Request("scenario", target, hours, forecast, pathway=pathway)


def from_output(request: Request, output: BatteryOutput, precomputed: bool) -> Result:
    """Per-MW summary and daily revenue from a 1 MW run."""
    s = output.summary["summary"]
    days = int(s["days"])
    benchmark = output.benchmark_daily if output.benchmark_daily is not None else output.daily
    daily = pd.DataFrame(
        {
            "revenue": output.daily["revenue"].to_numpy(),
            "benchmark_revenue": benchmark["revenue"].reindex(output.daily.index).to_numpy(),
        },
        index=pd.to_datetime(output.daily.index).strftime("%Y-%m-%d"),
    )
    benchmark_total = float(daily["benchmark_revenue"].sum())
    response = s.get("response_revenue")
    summary = {
        "days": days,
        "revenue_per_mw_year": float(s["revenue_per_mw_year"]),
        "perfect_per_mw_year": benchmark_total * DAYS_PER_YEAR / days,
        "capture_ratio": float(s["capture_ratio"]),
        "cycles_per_day": float(s["equivalent_cycles"]) / days,
        "captured_spread": float(s["captured_spread"] or 0.0),
        "forecast_mae": float(s["forecast_mae"]),
        "response_share": float(response) / float(s["revenue"]) if response else 0.0,
    }
    return Result(request, summary, daily, precomputed)


def live(request: Request, data: Path) -> Result:
    return from_output(request, run(request, data), precomputed=False)


def write(results: list[Result], data: Path) -> None:
    """Write the precomputed summary and daily files under ``data``."""
    rows, daily = [], []
    for result in results:
        r = result.request
        rows.append(
            {
                "key": r.key,
                "source": r.source,
                "year": r.year,
                "pathway": r.pathway or "",
                "hours": r.hours,
                "forecast": r.forecast,
                "services": r.services,
                **result.summary,
            }
        )
        frame = result.daily.reset_index(names="date")
        frame.insert(0, "key", r.key)
        daily.append(frame)
    (data / SUMMARY_FILE).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(data / SUMMARY_FILE, index=False, float_format="%.6g")
    pd.concat(daily).to_csv(data / DAILY_FILE, index=False, float_format="%.2f")


class Store:
    """The precomputed results, read once."""

    def __init__(self, data: Path) -> None:
        summary_path, daily_path = data / SUMMARY_FILE, data / DAILY_FILE
        if not summary_path.is_file() or not daily_path.is_file():
            raise DataError("precomputed app results not found")
        self.summary = pd.read_csv(summary_path, keep_default_na=False).set_index("key")
        daily = pd.read_csv(daily_path)
        self._daily = {key: frame.set_index("date") for key, frame in daily.groupby("key")}

    def get(self, request: Request) -> Result | None:
        if request.key not in self.summary.index:
            return None
        row = self.summary.loc[request.key].to_dict()
        summary = {name: float(row[name]) for name in SUMMARY_FIELDS}
        summary["days"] = int(row["days"])
        frame = self._daily[request.key][["revenue", "benchmark_revenue"]]
        return Result(request, summary, frame, precomputed=True)


SUMMARY_FIELDS = (
    "days",
    "revenue_per_mw_year",
    "perfect_per_mw_year",
    "capture_ratio",
    "cycles_per_day",
    "captured_spread",
    "forecast_mae",
    "response_share",
)


@cache
def store(data: Path) -> Store | None:
    try:
        return Store(data)
    except DataError:
        return None


def result(request: Request, data: Path) -> Result:
    """The precomputed result if there is one, else a live run."""
    found = store(data)
    cached = found.get(request) if found is not None else None
    return cached if cached is not None else live(request, data)
