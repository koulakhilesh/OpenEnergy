"""FastAPI routes: HTML pages and a JSON API on the same requests."""

from __future__ import annotations

import html
import logging
import os
from functools import cache
from pathlib import Path
from typing import Annotated

import pandas as pd
from fastapi import Depends, FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

import openenergy
from openenergy.app import results
from openenergy.app.runs import (
    HISTORY_YEARS,
    RESPONSE_FROM,
    SCENARIO_NOTE,
    SCENARIO_YEARS,
    ForecastName,
    Request,
    Services,
    Source,
    run,
)
from openenergy.data.fes import FES_ATTRIBUTION, PATHWAYS
from openenergy.errors import ConfigError, DataError
from openenergy.report import build_report

logger = logging.getLogger(__name__)
_STYLE = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1f2933}
main{max-width:900px;margin:0 auto;padding:16px 24px}
fieldset{border:1px solid #e4e7eb;margin:12px 0;padding:12px}label{margin-right:16px}
input,select{margin:4px 8px 4px 0}button{padding:6px 16px}
table{border-collapse:collapse;font-size:14px}th,td{border:1px solid #e4e7eb;padding:4px 8px}
td{text-align:right}td:first-child{text-align:left}th{background:#f5f7fa}
.source{color:#616e7c;font-size:12px}nav a{margin-right:12px}
"""
_FAILED = "The run could not be completed. Please check the inputs and try again."

app = FastAPI(title="OpenEnergy", version=openenergy.__version__, docs_url=None, redoc_url=None)


def data_dir() -> Path:
    return Path(os.environ.get("OPENENERGY_DATA", Path.cwd() / "data"))


def battery_request(
    source: Source = "history",
    year: Annotated[int, Query(ge=HISTORY_YEARS[0], le=HISTORY_YEARS[1])] = HISTORY_YEARS[1],
    pathway: str = "Holistic Transition",
    target: Annotated[int, Query(ge=SCENARIO_YEARS[0], le=SCENARIO_YEARS[1])] = 2030,
    hours: Annotated[float, Query(ge=0.5, le=8)] = 2.0,
    forecast: ForecastName = "naive_last_week",
    services: Services = "none",
) -> Request:
    if source == "history":
        return Request("history", year, hours, forecast, services)
    return Request("scenario", target, hours, forecast, services, pathway)


BatteryQuery = Annotated[Request, Depends(battery_request)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": openenergy.__version__}


@app.get("/api/result")
def api_result(request: BatteryQuery) -> JSONResponse:
    """Per-MW results for one battery: precomputed when available, else run now."""
    problem = request.problem()
    if problem is not None:
        return JSONResponse({"error": problem}, 400)
    try:
        found = results.result(request, data_dir())
    except ConfigError, DataError:
        logger.exception("Result failed")
        return JSONResponse({"error": _FAILED}, 400)
    return JSONResponse(found.to_dict())


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
and compares with perfect foresight. A run takes 15 to 45 seconds.</p>
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
    table = _fes_summary(data_dir())
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
    request: BatteryQuery, power_mw: Annotated[float, Query(gt=0, le=1000)] = 1.0
) -> HTMLResponse:
    problem = request.problem()
    if problem is not None:
        return HTMLResponse(_page("Cannot run", f"<p>{html.escape(problem)}</p>"), 400)
    try:
        output = run(request, data_dir(), power_mw)
    except ConfigError, DataError:
        logger.exception("Battery run failed")
        return HTMLResponse(_page("Cannot run", f"<p>{_FAILED}</p>"), 400)
    title = f"{power_mw:g} MW / {request.label}"
    return HTMLResponse(build_report([output], title=title, cdn=True))


@cache
def _fes_summary(data: Path) -> pd.DataFrame:
    return pd.read_csv(data / "scenarios/fes_summary.csv")


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
