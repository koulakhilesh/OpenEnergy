"""Storage saturation: how a battery's value falls as GB's battery fleet grows.

For a FES pathway and year, the FES battery fleet is scaled (``battery_scale``) and, for
each fleet size, the least firm peaking capacity is added that keeps the loss of load
expectation (hours with unserved energy, averaged over the weather years) within GB's
reliability standard. Each weather year is then solved once more at that capacity and a
reference battery is valued with perfect foresight on the modelled prices, its revenue
split into ordinary days and scarcity days (with an hour at ``SCARCITY_GBP_PER_MWH`` or more).

The firm capacity no longer needed as the fleet grows, per MW of batteries added, is the
fleet's equivalent firm capacity. Every system solve is a full year with unit commitment,
so a study is long; ``workers`` solves weather years in parallel processes.

Weather years start in 2024: a FES system is scaled from FES's own figures for the weather
year, which FES 2025 publishes from 2024. Two years make a thin expectation; earlier
weather years would need each technology's historic GB capacity, which is not yet in the
bundled data.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from openenergy.assets.battery import BatterySpec
from openenergy.backtest.engine import BacktestConfig, run_backtest
from openenergy.data.fes import FesSource
from openenergy.data.series import PriceSeries
from openenergy.dispatch.arbitrage import DispatchConfig
from openenergy.errors import ConfigError, DataError
from openenergy.forecast.baseline import PerfectForesight
from openenergy.metrics.summary import summarise
from openenergy.system.forward import fes_changes
from openenergy.system.scenario import (
    RELIABILITY_STANDARD_HOURS,
    SystemScenario,
    least_firm,
    run_system_scenario,
)
from openenergy.system.validate import DATA_END

SCALES = (0.0, 0.5, 1.0, 2.0, 3.0)
# FES is scaled from its own value for the weather year, and FES 2025 starts at 2024.
FES_FROM = 2024
WEATHER_YEARS = tuple(range(FES_FROM, DATA_END.year + 1))
SCARCITY_GBP_PER_MWH = 1000.0
REFERENCE = BatterySpec(power_mw=1, energy_mwh=2, eta_charge=0.95, eta_discharge=0.95)
WEAR_GBP_PER_MWH = 5.0
SATURATION_NOTE = (
    "Each FES pathway's system on each weather year with interconnector links and unit "
    "commitment; firm peaking capacity is added until the loss of load expectation over "
    "the weather years meets GB's reliability standard. The reference battery "
    "(1 MW / 2 MWh, 95% each way, GBP 5/MWh wear) is valued with perfect foresight on the "
    "modelled prices: an upper bound, and its value falls as the fleet it joins grows. "
    "Scarcity revenue is what it earns on days with an hour priced at GBP 1,000/MWh or more."
)


@dataclass(frozen=True)
class Point:
    """One system solve of the study."""

    data: Path
    pathway: str
    year: int
    weather_year: int
    battery_scale: float
    firm_mw: float
    window: tuple[str, str] | None = None


def solve_point(point: Point, value: bool = False) -> dict[str, Any]:
    """Solve one weather year; with ``value``, also value the reference battery on it."""
    system: dict[str, Any] = {
        "data": str(point.data),
        "year": point.weather_year,
        "interconnectors": "links",
        "commitment": True,
        "fes": {
            "pathway": point.pathway,
            "year": point.year,
            "firm_mw": point.firm_mw,
            "battery_scale": point.battery_scale,
        },
    }
    if point.window is not None:
        system["start"], system["end"] = (f"{point.weather_year}-{day}" for day in point.window)
    run = run_system_scenario(SystemScenario.model_validate({"name": "sat", "system": system}))
    s = run.summary
    row: dict[str, Any] = {
        "pathway": point.pathway,
        "year": point.year,
        "battery_scale": point.battery_scale,
        "weather_year": point.weather_year,
        "firm_added_mw": point.firm_mw,
        "fleet_battery_mw": s.storage_mw.get("fes_battery", 0.0),
        "unserved_hours": s.unserved_hours,
    }
    if not value:
        return row
    price = run.result.price_of(run.scenario.system.price)
    prices = PriceSeries(price, currency="GBP", zone="GB_GBN")
    config = BacktestConfig(dispatch=DispatchConfig(degradation_cost=WEAR_GBP_PER_MWH))
    battery = run_backtest(REFERENCE, prices, PerfectForesight(prices), config)
    summary = summarise(battery)
    # Each day ends as full as it began, so daily revenue adds up: split it by whether the
    # day had a scarcity hour.
    peak = price.groupby(pd.DatetimeIndex(price.index).date).max()
    daily = battery.daily["revenue"]
    scarce = daily[peak.reindex(daily.index).to_numpy() >= SCARCITY_GBP_PER_MWH].sum()
    total = daily.sum()
    per_mw = summary.revenue_per_mw_year or 0.0
    row |= {
        "unserved_gwh": s.unserved_mwh / 1000,
        "price_mean": s.price_mean,
        "daily_spread": s.daily_spread,
        "scarcity_hours": int((price >= SCARCITY_GBP_PER_MWH).sum()),
        "scarcity_days": int((peak >= SCARCITY_GBP_PER_MWH).sum()),
        "curtailment_twh": s.curtailment_twh,
        "emissions_mt": s.emissions_mt,
        "fleet_cycles": s.storage_cycles.get("fes_battery", 0.0),
        "revenue_per_mw_year": per_mw,
        "scarcity_revenue": per_mw * float(scarce / total) if total > 0 else 0.0,
        "battery_cycles": summary.equivalent_cycles,
    }
    return row


def _solve_unvalued(point: Point) -> dict[str, Any]:
    return solve_point(point)


def _solve_valued(point: Point) -> dict[str, Any]:
    return solve_point(point, value=True)


def secure_points(
    pool: Executor,
    data: Path,
    pathway: str,
    year: int,
    battery_scale: float,
    weather_years: Sequence[int],
    lole_hours: float = RELIABILITY_STANDARD_HOURS,
    window: tuple[str, str] | None = None,
) -> list[Point]:
    """The weather years at the least firm capacity whose mean loss of load meets the standard."""

    def points(firm: float) -> list[Point]:
        return [Point(data, pathway, year, w, battery_scale, firm, window) for w in weather_years]

    def meets(firm: float) -> bool:
        hours = [int(row["unserved_hours"]) for row in pool.map(_solve_unvalued, points(firm))]
        return sum(hours) / len(hours) <= lole_hours

    return points(least_firm(meets))


def unusable(data: str | Path, pathway: str, year: int, weather_years: Sequence[int]) -> str | None:
    """Why a pathway cannot be scaled from one of the weather years, or None."""
    source = FesSource(Path(data).parent / "fes")
    for weather in weather_years:
        try:
            fes_changes(source, pathway, year, weather, {"ccgt": 0.0, "peaking": 0.0}, 0.85, 0.75)
        except (ConfigError, DataError) as exc:
            return f"{pathway} on {weather} weather: {exc}"
    return None


def saturation_study(
    data: str | Path,
    pathways: Sequence[str],
    year: int = 2035,
    scales: Sequence[float] = SCALES,
    weather_years: Sequence[int] = WEATHER_YEARS,
    lole_hours: float = RELIABILITY_STANDARD_HOURS,
    workers: int = 1,
    progress: Callable[[str], None] | None = None,
    window: tuple[str, str] | None = None,
    known_firm: Mapping[tuple[str, float], float] | None = None,
) -> pd.DataFrame:
    """One row per pathway, fleet scale and weather year (see the module docstring).

    ``window`` (``("MM-DD", "MM-DD")``) solves only those days of each weather year, and the
    standard then applies to that window: for quick looks and tests, not for results.
    Searches for several pathways and scales run at once when ``workers`` exceeds the
    number of weather years. ``known_firm`` maps (pathway, scale) to firm capacity already
    found (see ``firm_from``), which skips that search.
    """
    combos = [(pathway, scale) for pathway in pathways for scale in scales]
    for pathway in pathways:
        problem = unusable(data, pathway, year, weather_years)
        if problem is not None:
            raise ConfigError(problem)

    def one(combo: tuple[str, float]) -> list[dict[str, Any]]:
        pathway, scale = combo
        if known_firm is not None and combo in known_firm:
            chosen = [
                Point(Path(data), pathway, year, w, scale, known_firm[combo], window)
                for w in weather_years
            ]
        else:
            chosen = secure_points(
                pool, Path(data), pathway, year, scale, weather_years, lole_hours, window
            )
        found = list(pool.map(_solve_valued, chosen))
        if progress is not None:
            progress(f"{pathway} x{scale:g}: {chosen[0].firm_mw:,.0f} MW firm added")
        return found

    searches = max(1, workers // max(1, len(weather_years)))
    with ProcessPoolExecutor(max_workers=workers) as pool, ThreadPoolExecutor(searches) as runs:
        rows = [row for found in runs.map(one, combos) for row in found]
    return pd.DataFrame(rows)


def firm_from(path: str | Path, year: int) -> dict[tuple[str, float], float]:
    """Firm capacity per (pathway, scale) from an earlier study's ``saturation_years.csv``."""
    rows = pd.read_csv(path)
    rows = rows[rows["year"] == year].drop_duplicates(["pathway", "battery_scale"])
    return {
        (str(p), float(s)): float(f)
        for p, s, f in zip(
            rows["pathway"], rows["battery_scale"], rows["firm_added_mw"], strict=True
        )
    }


def saturation_summary(rows: pd.DataFrame) -> pd.DataFrame:
    """Mean over weather years per pathway and fleet scale, with equivalent firm capacity.

    ``lole_hours`` is the mean of the hours with unserved energy. ``equivalent_firm`` is the
    firm capacity saved against no FES batteries per MW of batteries (needs scale 0).
    """
    keys = ["pathway", "year", "battery_scale"]
    table = rows.groupby(keys, as_index=False).mean(numeric_only=True)
    table = table.drop(columns="weather_year").rename(columns={"unserved_hours": "lole_hours"})
    none = table.loc[table["battery_scale"] == 0, ["pathway", "year", "firm_added_mw"]]
    base = table[["pathway", "year"]].merge(
        none.rename(columns={"firm_added_mw": "base"}), how="left"
    )["base"]
    saved = base.to_numpy() - table["firm_added_mw"].to_numpy()
    table["equivalent_firm"] = (saved / table["fleet_battery_mw"]).where(
        table["fleet_battery_mw"] > 0
    )
    return table
