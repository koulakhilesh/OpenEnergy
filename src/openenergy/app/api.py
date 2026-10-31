"""JSON API for the web front end; the OpenAPI schema is what its types are generated from."""

from __future__ import annotations

import logging
import os
from functools import cache
from pathlib import Path
from typing import Annotated, Literal

import pandas as pd
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import openenergy
from openenergy.app import results, text
from openenergy.app.results import PRECOMPUTED_HOURS, Result
from openenergy.app.runs import (
    FUNDAMENTALS_FROM,
    HISTORY_YEARS,
    RESPONSE_FROM,
    SCENARIO_NOTE,
    SCENARIO_YEARS,
    ForecastName,
    Request,
    Services,
    Source,
    from_prices,
)
from openenergy.data.fes import FES_ATTRIBUTION, PATHWAYS
from openenergy.errors import ConfigError, DataError

logger = logging.getLogger(__name__)
FAILED = "The run could not be completed. Please check the inputs and try again."
HOURS = (0.5, 8.0)
POWER_MW = (0.1, 1000.0)
DOCS_URL = "https://koulakhilesh.github.io/OpenEnergy/"

router = APIRouter(prefix="/api")


def data_dir() -> Path:
    return Path(os.environ.get("OPENENERGY_DATA", Path.cwd() / "data"))


def battery_request(
    source: Source = "history",
    year: Annotated[int, Query(ge=HISTORY_YEARS[0], le=HISTORY_YEARS[1])] = HISTORY_YEARS[1],
    pathway: str = "Holistic Transition",
    target: Annotated[int, Query(ge=SCENARIO_YEARS[0], le=SCENARIO_YEARS[1])] = 2030,
    hours: Annotated[float, Query(ge=HOURS[0], le=HOURS[1])] = 2.0,
    forecast: ForecastName = "naive_last_week",
    services: Services = "none",
) -> Request:
    if source == "history":
        return Request("history", year, hours, forecast, services)
    return Request("scenario", target, hours, forecast, services, pathway)


BatteryQuery = Annotated[Request, Depends(battery_request)]
PowerQuery = Annotated[float, Query(ge=POWER_MW[0], le=POWER_MW[1])]
HoursChoice = Literal["1", "2", "4"]


class Error(BaseModel):
    error: str


class Options(BaseModel):
    version: str
    history_years: list[int]
    response_from: int
    pathways: list[str]
    scenario_years: list[int]
    precomputed_hours: list[float]
    hours_range: tuple[float, float]
    power_range: tuple[float, float]
    forecasts: dict[str, str]
    services: dict[str, str]
    help: dict[str, str]
    docs_url: str


class RequestOut(BaseModel):
    source: Source
    year: int
    pathway: str | None
    hours: float
    forecast: ForecastName
    services: Services
    key: str
    prices: str
    where: str
    label: str


class Summary(BaseModel):
    days: int
    revenue_per_mw_year: float
    perfect_per_mw_year: float
    capture_ratio: float
    cycles_per_day: float
    captured_spread: float
    forecast_mae: float
    response_share: float


class Daily(BaseModel):
    date: list[str]
    revenue: list[float]
    benchmark_revenue: list[float]


class Wording(BaseModel):
    """Plain text for ``power_mw``: the answer sentence, assumptions and data sources."""

    power_mw: float
    answer: str
    assumptions: list[str]
    sources: str


class ResultOut(BaseModel):
    key: str
    label: str
    precomputed: bool
    request: RequestOut
    summary: Summary
    daily: Daily
    text: Wording


class Item(BaseModel):
    request: RequestOut
    summary: Summary


class Explore(BaseModel):
    history: list[Item]
    pathways: list[Item]


class Compare(BaseModel):
    options: list[RequestOut]
    results: list[ResultOut]


class PathwayRow(BaseModel):
    pathway: str
    year: int
    weather_year: int
    price_mean: float
    daily_spread: float
    imports_twh: float
    exports_twh: float
    curtailment_twh: float
    unserved_gwh: float
    unserved_hours: int
    firm_added_mw: float
    emissions_mt: float
    fes_imports_twh: float
    fes_exports_twh: float
    fes_curtailment_twh: float


class Scenarios(BaseModel):
    rows: list[PathwayRow]
    note: str
    attribution: str


_ERRORS: dict[int | str, dict[str, object]] = {400: {"model": Error}}


@router.get("/options")
def options() -> Options:
    """Everything the front end offers: years, pathways, limits and the "?" explanations."""
    return Options(
        version=openenergy.__version__,
        history_years=list(range(HISTORY_YEARS[0], HISTORY_YEARS[1] + 1)),
        response_from=RESPONSE_FROM,
        pathways=list(PATHWAYS),
        scenario_years=list(SCENARIO_YEARS),
        precomputed_hours=list(PRECOMPUTED_HOURS),
        hours_range=HOURS,
        power_range=POWER_MW,
        forecasts={
            "naive_last_week": "last week's prices",
            "fundamentals": f"OpenEnergy forecast (from {FUNDAMENTALS_FROM})",
            "perfect_foresight": "perfect foresight",
        },
        services={"none": "none", **text.SERVICE_NAMES},
        help=text.HELP,
        docs_url=DOCS_URL,
    )


@router.get("/result", response_model=ResultOut, responses=_ERRORS)
def result(request: BatteryQuery, power_mw: PowerQuery = 1.0) -> ResultOut | JSONResponse:
    """Per-MW results for one battery: precomputed when available, else run now."""
    found = find(request)
    if isinstance(found, str):
        return JSONResponse({"error": found}, 400)
    return result_out(found, power_mw)


@router.get("/explore", response_model=Explore, responses={503: {"model": Error}})
def explore(
    hours: HoursChoice = "2",
    forecast: ForecastName = "naive_last_week",
    services: Services = "none",
) -> Explore | JSONResponse:
    """Value by GB year (with ``services``) and by FES pathway, from the precomputed results."""
    store = results.store(data_dir())
    if store is None:
        return JSONResponse({"error": "Precomputed results are missing."}, 503)
    found = [store.get(r) for r in store.requests(float(hours), forecast)]
    items = [x for x in found if x is not None]
    return Explore(
        history=[
            item(x)
            for x in items
            if x.request.source == "history" and x.request.services == services
        ],
        pathways=[item(x) for x in items if x.request.source == "scenario"],
    )


@router.get("/compare", response_model=Compare, responses={**_ERRORS, 503: {"model": Error}})
def compare(
    item_: Annotated[list[str], Query(alias="item", max_length=3)] = [],  # noqa: B006
    hours: HoursChoice = "2",
    forecast: ForecastName = "naive_last_week",
    power_mw: PowerQuery = 1.0,
) -> Compare | JSONResponse:
    """Up to three precomputed results, named by their ``prices`` token, and every option."""
    store = results.store(data_dir())
    if store is None:
        return JSONResponse({"error": "Precomputed results are missing."}, 503)
    chosen = [from_prices(token, float(hours), forecast) for token in item_ if token]
    if any(request is None for request in chosen):
        return JSONResponse({"error": "Choose from the lists offered."}, 400)
    found = [store.get(request) for request in chosen if request is not None]
    return Compare(
        options=[request_out(r) for r in store.requests(float(hours), forecast)],
        results=[result_out(x, power_mw) for x in found if x is not None],
    )


@router.get("/scenarios")
def scenarios() -> Scenarios:
    """Each FES pathway's modelled results on the weather year next to NESO's own figures."""
    table = _fes_summary(data_dir())
    return Scenarios(
        rows=[PathwayRow.model_validate(row) for row in table.to_dict("records")],
        note=SCENARIO_NOTE,
        attribution=FES_ATTRIBUTION,
    )


def find(request: Request) -> Result | str:
    """The result, or a fixed message that is safe to show."""
    problem = request.problem()
    if problem is not None:
        return problem
    try:
        return results.result(request, data_dir())
    except ConfigError, DataError:
        logger.exception("Result failed")
        return FAILED


def request_out(request: Request) -> RequestOut:
    return RequestOut(
        source=request.source,
        year=request.year,
        pathway=request.pathway,
        hours=request.hours,
        forecast=request.forecast,
        services=request.services,
        key=request.key,
        prices=request.prices,
        where=request.where,
        label=request.label,
    )


def item(found: Result) -> Item:
    return Item(request=request_out(found.request), summary=Summary(**found.summary))


def result_out(found: Result, power_mw: float) -> ResultOut:
    return ResultOut(
        key=found.request.key,
        label=found.request.label,
        precomputed=found.precomputed,
        request=request_out(found.request),
        summary=Summary(**found.summary),
        daily=Daily(
            date=list(found.daily.index),
            revenue=found.daily["revenue"].round(2).tolist(),
            benchmark_revenue=found.daily["benchmark_revenue"].round(2).tolist(),
        ),
        text=Wording(
            power_mw=power_mw,
            answer=text.answer(found, power_mw),
            assumptions=text.assumptions(found.request, found.summary),
            sources=text.sources(found.request),
        ),
    )


@cache
def _fes_summary(data: Path) -> pd.DataFrame:
    return pd.read_csv(data / "scenarios/fes_summary.csv")
