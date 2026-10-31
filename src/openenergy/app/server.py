"""FastAPI app: the JSON API, downloads, the hourly report, and the built web front end."""

from __future__ import annotations

import html
import logging
import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

import openenergy
from openenergy.app import api, text
from openenergy.app.api import BatteryQuery, PowerQuery, data_dir, find
from openenergy.app.runs import run
from openenergy.errors import ConfigError, DataError
from openenergy.report import build_report

logger = logging.getLogger(__name__)
# Front-end routes; each serves the same page and the browser reads the query string.
PAGES = (
    "/",
    "/play",
    "/2035",
    "/research",
    # v6.0 addresses: the front end shows the simulator and keeps their query.
    "/lab",
    "/replay",
    "/run",
    "/result",
    "/explore",
    "/compare",
    "/scenarios",
    "/embed/arbitrage",
)
_MISSING = (
    "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>OpenEnergy</title>"
    "</head><body><h1>OpenEnergy</h1><p>The web front end is not built. From the repository "
    "folder run <code>npm --prefix web ci</code> and <code>npm --prefix web run build</code>, "
    "or use the JSON API at <a href='/api/options'>/api/options</a>.</p></body></html>"
)

app = FastAPI(title="OpenEnergy", version=openenergy.__version__, docs_url=None, redoc_url=None)
app.include_router(api.router)


def web_dir() -> Path:
    return Path(os.environ.get("OPENENERGY_WEB", Path.cwd() / "web/dist"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": openenergy.__version__}


@app.get("/download/daily.csv", response_class=PlainTextResponse)
def download_daily(request: BatteryQuery, power_mw: PowerQuery = 1.0) -> PlainTextResponse:
    found = find(request)
    if isinstance(found, str):
        return PlainTextResponse(found, 400)
    return PlainTextResponse(
        text.daily_csv(found, power_mw),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{request.key}.csv"'},
    )


@app.get("/download/scenario.yaml", response_class=PlainTextResponse)
def download_scenario(request: BatteryQuery, power_mw: PowerQuery = 1.0) -> PlainTextResponse:
    problem = request.problem()
    if problem is not None:
        return PlainTextResponse(problem, 400)
    return PlainTextResponse(
        text.scenario_yaml(request, power_mw),
        media_type="application/yaml",
        headers={"Content-Disposition": f'attachment; filename="{request.key}.yaml"'},
    )


@app.get("/battery", response_class=HTMLResponse)
def battery(
    request: BatteryQuery, power_mw: Annotated[float, Query(gt=0, le=1000)] = 1.0
) -> HTMLResponse:
    """The full hourly report for one battery, run now."""
    problem = request.problem()
    if problem is not None:
        return HTMLResponse(_message("Cannot run", problem), 400)
    try:
        output = run(request, data_dir(), power_mw)
    except ConfigError, DataError:
        logger.exception("Battery run failed")
        return HTMLResponse(_message("Cannot run", api.FAILED), 400)
    title = f"{power_mw:g} MW / {request.label}"
    return HTMLResponse(build_report([output], title=title, cdn=True))


def _page() -> FileResponse | HTMLResponse:
    index = web_dir() / "index.html"
    if not index.is_file():
        return HTMLResponse(_MISSING, 503)
    return FileResponse(index, media_type="text/html")


for _path in PAGES:
    app.add_api_route(_path, _page, methods=["GET"], include_in_schema=False, response_model=None)


@app.get("/assets/{name:path}", include_in_schema=False, response_model=None)
def assets(name: str) -> FileResponse | PlainTextResponse:
    """Hashed build files, looked up by name among the files in the assets folder."""
    return _listed(web_dir() / "assets", name, "public, max-age=31536000, immutable")


@app.get("/data/{name:path}", include_in_schema=False, response_model=None)
def static_data(name: str) -> FileResponse | PlainTextResponse:
    """Prices, generation mix and study results for the in-browser pages."""
    return _listed(web_dir() / "data", name, "public, max-age=86400")


def _listed(folder: Path, name: str, cache: str) -> FileResponse | PlainTextResponse:
    # Only names of files actually in the folder are served, never a path built from input.
    files = {p.name: p for p in folder.iterdir() if p.is_file()} if folder.is_dir() else {}
    path = files.get(name)
    if path is None:
        return PlainTextResponse("Not found", 404)
    return FileResponse(path, headers={"Cache-Control": cache})


def _message(title: str, body: str) -> str:
    return (
        f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{html.escape(title)}"
        f"</title></head><body><h1>{html.escape(title)}</h1><p>{html.escape(body)}</p>"
        "<p><a href='/'>Back to OpenEnergy</a></p></body></html>"
    )
