"""Read the outputs written by ``run``, ``system run``, ``system validate`` and ``sweep``."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from openenergy.errors import DataError

SWEEP_COLUMNS = ("total", "revenue_per_mw_year", "capture_ratio", "equivalent_cycles")


@dataclass(frozen=True, eq=False)
class BatteryOutput:
    """A battery or co-located site backtest (``openenergy run``)."""

    name: str
    summary: dict[str, Any]
    daily: pd.DataFrame = field(repr=False)
    intervals: pd.DataFrame = field(repr=False)
    benchmark_daily: pd.DataFrame | None = field(default=None, repr=False)


@dataclass(frozen=True, eq=False)
class SystemOutput:
    """One GB system scenario year (``openenergy system run``)."""

    name: str
    summary: dict[str, Any]
    dispatch: pd.DataFrame = field(repr=False)


@dataclass(frozen=True, eq=False)
class BackcastOutput:
    """A system backcast (``openenergy system validate``)."""

    name: str
    summary: dict[str, Any]
    years: pd.DataFrame = field(repr=False)
    hourly: pd.DataFrame = field(repr=False)


@dataclass(frozen=True, eq=False)
class SweepOutput:
    """A sweep results table; ``keys`` are the swept settings, in column order."""

    name: str
    table: pd.DataFrame = field(repr=False)
    keys: list[str]


Output = BatteryOutput | SystemOutput | BackcastOutput | SweepOutput


def load_output(path: str | Path) -> Output:
    """Read one output directory (or a sweep CSV), detecting its kind from the files."""
    path = Path(path)
    if path.is_file():
        return _sweep(path)
    if not path.is_dir():
        raise DataError(f"no output directory or sweep CSV at {path}")
    if (path / "daily.csv").is_file():
        summary = _summary(path)
        benchmark = path / "benchmark_daily.csv"
        return BatteryOutput(
            name=str(summary.get("scenario", path.name)),
            summary=summary,
            daily=_csv(path / "daily.csv", "date"),
            intervals=_csv(path / "intervals.csv", "timestamp", utc=True),
            benchmark_daily=_csv(benchmark, "date") if benchmark.is_file() else None,
        )
    if (path / "dispatch.csv").is_file():
        summary = _summary(path)
        return SystemOutput(
            name=str(summary.get("scenario", path.name)),
            summary=summary,
            dispatch=_csv(path / "dispatch.csv", "utc_timestamp", utc=True),
        )
    if (path / "backcast.csv").is_file():
        return BackcastOutput(
            name=path.name,
            summary=_summary(path),
            years=pd.read_csv(path / "backcast.csv"),
            hourly=_csv(path / "hourly.csv", "utc_timestamp", utc=True),
        )
    raise DataError(
        f"{path} has no daily.csv, dispatch.csv or backcast.csv; "
        "pass a directory written by run, system run or system validate, or a sweep CSV"
    )


def _sweep(path: Path) -> SweepOutput:
    table = pd.read_csv(path)
    missing = [column for column in SWEEP_COLUMNS if column not in table.columns]
    if missing:
        raise DataError(f"{path.name} is not a sweep CSV: missing {', '.join(missing)}")
    keys = list(table.columns[: list(table.columns).index("total")])
    return SweepOutput(name=path.stem, table=table, keys=keys)


def _summary(directory: Path) -> dict[str, Any]:
    path = directory / "summary.json"
    if not path.is_file():
        raise DataError(f"{directory} has no summary.json")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise DataError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DataError(f"{path} must hold a JSON object")
    return data


def _csv(path: Path, index: str, utc: bool = False) -> pd.DataFrame:
    """A CSV indexed by its date (``utc=False``) or UTC timestamp column."""
    if not path.is_file():
        raise DataError(f"missing {path}")
    frame = pd.read_csv(path)
    if index not in frame.columns:
        raise DataError(f"{path.name} has no {index!r} column")
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.pop(index), utc=utc))
    return frame
