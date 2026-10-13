"""Web app: value a battery on historic GB prices or on a NESO FES pathway's modelled prices.

Run locally with ``uv run uvicorn openenergy.app:app``; Vercel serves ``app.py`` at the
repository root. Data are read from ``$OPENENERGY_DATA`` or ``./data``.
"""

from __future__ import annotations

import html
import logging
import os
import tempfile
from datetime import date
from functools import cache
from pathlib import Path
from typing import Annotated, Literal

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

import openenergy
from openenergy.assets.battery import BatterySpec
from openenergy.backtest.engine import BacktestConfig, run_backtest
from openenergy.data.fes import FES_ATTRIBUTION, PATHWAYS
from openenergy.data.fleet import FLEET_ATTRIBUTION
from openenergy.data.interconnectors import INTERCONNECTOR_ATTRIBUTION
from openenergy.data.neso import MIX_ATTRIBUTION
from openenergy.data.series import PriceSeries
from openenergy.dispatch.arbitrage import DispatchConfig
from openenergy.errors import ConfigError, DataError
from openenergy.forecast.baseline import Forecaster, NaiveLastWeek, PerfectForesight
from openenergy.metrics.summary import summarise
from openenergy.report import build_report
from openenergy.report.load import BatteryOutput, load_output
from openenergy.scenario import Scenario, run_scenario, write_outputs
from openenergy.system.forward import FES_NOTE, LINKS_NOTE, price_column
from openenergy.system.scenario import SYSTEM_NOTE

HISTORY_YEARS = (2017, 2025)
RESPONSE_FROM = 2022

logger = logging.getLogger(__name__)
SCENARIO_YEARS = (2030, 2035)
WEATHER_YEAR = 2025
SERVICES = {"none": [], "dc": ["DCL", "DCH"], "dc_dm": ["DCL", "DCH", "DML", "DMH"]}
DEGRADATION_COST = 5.0
SCENARIO_NOTE = (
    f"Prices are OpenEnergy's model of GB with this pathway's fleet and demand on "
    f"{WEATHER_YEAR}'s weather and fuel, carbon and neighbouring prices, not a forecast. "
    f"{SYSTEM_NOTE} {FES_NOTE} {LINKS_NOTE}"
)
_STYLE = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1f2933}
main{max-width:900px;margin:0 auto;padding:16px 24px}
fieldset{border:1px solid #e4e7eb;margin:12px 0;padding:12px}label{margin-right:16px}
input,select{margin:4px 8px 4px 0}button{padding:6px 16px}
table{border-collapse:collapse;font-size:14px}th,td{border:1px solid #e4e7eb;padding:4px 8px}
td{text-align:right}td:first-child{text-align:left}th{background:#f5f7fa}
.source{color:#616e7c;font-size:12px}nav a{margin-right:12px}
"""

app = FastAPI(title="OpenEnergy", version=openenergy.__version__, docs_url=None, redoc_url=None)


def data_dir() -> Path:
    return Path(os.environ.get("OPENENERGY_DATA", Path.cwd() / "data"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": openenergy.__version__}


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    years = "".join(
        f"<option{' selected' if y == HISTORY_YEARS[1] else ''}>{y}</option>"
        for y in range(HISTORY_YEARS[0], HISTORY_YEARS[1] + 1)
    )
    pathways = "".join(f"<option>{html.escape(p)}</option>" for p in PATHWAYS)
    targets = "".join(f"<option>{y}</option>" for y in SCENARIO_YEARS)
    form = f"""
<h1>OpenEnergy battery value</h1>
<p>What would a grid battery have earned trading GB day-ahead prices, or what might it earn
on a NESO Future Energy Scenarios pathway? Each run plans every day at noon the day before
and compares with perfect foresight. About 10 to 30 seconds per run.</p>
<form action="/battery" method="get">
<fieldset><legend>Prices</legend>
<label><input type="radio" name="source" value="history" checked> Historic GB year
<select name="year">{years}</select></label><br>
<label><input type="radio" name="source" value="scenario"> FES pathway
<select name="pathway">{pathways}</select> in <select name="target">{targets}</select></label>
</fieldset>
<fieldset><legend>Battery and plan</legend>
<label>Power (MW) <input name="power_mw" type="number" value="1" min="0.1" max="1000"
step="0.1"></label>
<label>Duration (hours) <input name="hours" type="number" value="2" min="0.5" max="8"
step="0.5"></label><br>
<label>Forecast <select name="forecast"><option value="naive_last_week">last week's prices
</option><option value="perfect_foresight">perfect foresight</option></select></label>
<label>Frequency response (historic {RESPONSE_FROM} onwards)
<select name="services"><option value="none">none</option>
<option value="dc">Dynamic Containment</option>
<option value="dc_dm">Dynamic Containment and Moderation</option></select></label>
</fieldset>
<button type="submit">Run</button>
</form>"""
    return _page("OpenEnergy", form)


@app.get("/scenarios", response_class=HTMLResponse)
def scenarios() -> str:
    table = _summary()
    header = (
        "<tr><th>Pathway</th><th>Year</th><th>Mean price</th><th>Daily spread</th>"
        "<th>Imports</th><th>FES imports</th><th>Exports</th><th>FES exports</th>"
        "<th>Curtailment</th><th>FES curtailment</th><th>Unserved (GWh)</th></tr>"
    )
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(r.pathway))}</td><td>{r.year}</td><td>{r.price_mean:.1f}</td>"
        f"<td>{r.daily_spread:.1f}</td><td>{r.imports_twh:.1f}</td>"
        f"<td>{r.fes_imports_twh:.1f}</td><td>{r.exports_twh:.1f}</td>"
        f"<td>{r.fes_exports_twh:.1f}</td><td>{r.curtailment_twh:.1f}</td>"
        f"<td>{r.fes_curtailment_twh:.1f}</td><td>{r.unserved_gwh:.1f}</td></tr>"
        for r in table.itertuples()
    )
    body = (
        "<h1>FES pathways on 2025's weather</h1>"
        "<p>Prices in GBP/MWh, energy in TWh. FES columns are NESO's own figures for the "
        "same year; the model's are from one weather year with price-taking links, so the "
        "gaps are part of the result.</p>"
        f"<table>{header}{rows}</table>"
        f'<p class="source">{html.escape(SCENARIO_NOTE)}</p>'
        f'<p class="source">{html.escape(FES_ATTRIBUTION)}</p>'
    )
    return _page("FES pathways", body)


@app.get("/battery", response_class=HTMLResponse)
def battery(
    source: Literal["history", "scenario"] = "history",
    year: Annotated[int, Query(ge=HISTORY_YEARS[0], le=HISTORY_YEARS[1])] = HISTORY_YEARS[1],
    pathway: str = "Holistic Transition",
    target: Annotated[int, Query(ge=SCENARIO_YEARS[0], le=SCENARIO_YEARS[1])] = 2030,
    power_mw: Annotated[float, Query(gt=0, le=1000)] = 1.0,
    hours: Annotated[float, Query(ge=0.5, le=8)] = 2.0,
    forecast: Literal["naive_last_week", "perfect_foresight"] = "naive_last_week",
    services: Literal["none", "dc", "dc_dm"] = "none",
) -> HTMLResponse:
    spec = BatterySpec(power_mw=power_mw, energy_mwh=power_mw * hours)
    try:
        if source == "history":
            output = _history(spec, year, forecast, services)
            title = f"{power_mw:g} MW / {hours:g} h battery, GB {year}"
        else:
            if pathway not in PATHWAYS or target not in SCENARIO_YEARS:
                raise ConfigError("choose a FES pathway and 2030 or 2035")
            if services != "none":
                raise ConfigError("frequency response is available on historic years only")
            output = _scenario(spec, pathway, target, forecast)
            title = f"{power_mw:g} MW / {hours:g} h battery, {pathway} {target}"
    except (ConfigError, DataError) as exc:
        logger.exception("Battery run failed")
        return HTMLResponse(
            _page("Cannot run", "<p>The request could not be processed. Please check inputs and try again.</p>"),
            400,
        )
    return HTMLResponse(build_report([output], title=title, cdn=True))


def _history(spec: BatterySpec, year: int, forecast: str, services: str) -> BatteryOutput:
    data = data_dir()
    raw: dict[str, object] = {
        "name": f"gb-{year}",
        "data": {
            "source": "ember",
            "path": str(data / "prices/gb_day_ahead_ember.csv"),
            "start": date(year, 1, 1),
            "end": date(year, 12, 31),
        },
        "battery": {"power_mw": spec.power_mw, "energy_mwh": spec.energy_mwh},
        "forecast": forecast,
        "dispatch": {"degradation_cost": DEGRADATION_COST},
    }
    if services != "none":
        if year < RESPONSE_FROM:
            raise ConfigError(f"frequency response needs a year from {RESPONSE_FROM}")
        raw["response"] = {
            "path": str(data / "response/gb_dynamic_response.csv"),
            "services": SERVICES[services],
        }
    scenario = Scenario.model_validate(raw, context={"base": data})
    with tempfile.TemporaryDirectory() as tmp:
        output = load_output(write_outputs(run_scenario(scenario), Path(tmp) / "run"))
    if not isinstance(output, BatteryOutput):
        raise DataError("unexpected output")
    return output


def _scenario(spec: BatterySpec, pathway: str, target: int, forecast: str) -> BatteryOutput:
    column = price_column(pathway, target)
    prices = PriceSeries(_fes_prices()[column].rename(None), currency="GBP", zone="GB_GBN")
    config = BacktestConfig(dispatch=DispatchConfig(degradation_cost=DEGRADATION_COST))
    perfect = PerfectForesight(prices)
    forecaster: Forecaster = perfect if forecast == "perfect_foresight" else NaiveLastWeek()
    run = run_backtest(spec, prices, forecaster, config)
    benchmark = (
        run
        if forecaster is perfect
        else run_backtest(spec, prices, perfect, config, list(run.daily.index))
    )
    attribution = " ".join(
        (MIX_ATTRIBUTION, FLEET_ATTRIBUTION, INTERCONNECTOR_ATTRIBUTION, FES_ATTRIBUTION)
    )
    return BatteryOutput(
        name=column,
        summary={
            "summary": summarise(run, benchmark=benchmark).to_dict(),
            "note": SCENARIO_NOTE,
            "attribution": attribution,
        },
        daily=run.daily,
        intervals=run.intervals,
        benchmark_daily=None if benchmark is run else benchmark.daily,
    )


@cache
def _fes_prices() -> pd.DataFrame:
    path = data_dir() / "scenarios/fes_prices.csv"
    if not path.is_file():
        raise DataError(f"precomputed scenario prices not found: {path.name}")
    frame = pd.read_csv(path, index_col="utc_timestamp")
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, format="ISO8601"))
    return frame


@cache
def _summary() -> pd.DataFrame:
    return pd.read_csv(data_dir() / "scenarios/fes_summary.csv")


def _page(title: str, body: str) -> str:
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head><body><main>"
        '<nav><a href="/">Battery value</a><a href="/scenarios">FES pathways</a>'
        '<a href="https://koulakhilesh.github.io/OpenEnergy/">Docs</a></nav>'
        f'{body}<p class="source">OpenEnergy {html.escape(openenergy.__version__)}. '
        "Code MIT; data keep their own licences, credited with each result.</p>"
        "</main></body></html>\n"
    )
