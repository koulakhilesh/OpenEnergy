"""HTML for the app's result page: the answer first, then charts, assumptions and downloads."""

from __future__ import annotations

import html
import math
from urllib.parse import urlencode

import pandas as pd
import plotly.graph_objects as go
import yaml
from plotly.offline import get_plotlyjs_version

from openenergy.app.results import Result
from openenergy.app.runs import (
    DEGRADATION_COST,
    SCENARIO_ATTRIBUTION,
    SERVICES,
    WEATHER_YEAR,
    Request,
)
from openenergy.data.ember import EMBER_ATTRIBUTION
from openenergy.data.response import RESPONSE_ATTRIBUTION
from openenergy.report import figures

PLOTLY_JS = f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"
SERVICE_NAMES = {
    "dc": "Dynamic Containment",
    "dc_dm": "Dynamic Containment and Moderation",
}
MODEL_SPREAD_SHARE = 0.6  # modelled 2025 daily spread / actual (forward scenarios guide)


def query(request: Request, power_mw: float) -> str:
    """URL parameters that reproduce ``request`` for ``power_mw``."""
    params: dict[str, str | float | int] = {
        "source": request.source,
        "hours": f"{request.hours:g}",
        "forecast": request.forecast,
        "services": request.services,
        "power_mw": f"{power_mw:g}",
    }
    if request.source == "history":
        params["year"] = request.year
    else:
        params["pathway"] = str(request.pathway)
        params["target"] = request.year
    return urlencode(params)


def answer(result: Result, power_mw: float) -> str:
    """One plain sentence with the result, for anyone."""
    r, s = result.request, result.summary
    battery = f"A {power_mw:g} MW, {r.hours:g}-hour battery"
    if r.source == "history":
        where = f"trading GB day-ahead prices in {r.year}"
        if r.services != "none":
            where += f" and selling {SERVICE_NAMES[r.services]}"
        verb = "would have earned"
    else:
        where = f"on modelled GB prices for NESO's {r.pathway} pathway in {r.year}"
        verb = "would earn"
    total = s["revenue_per_mw_year"] * power_mw
    perfect = s["perfect_per_mw_year"] * power_mw
    if r.forecast == "naive_last_week":
        how = (
            f"planning each day on last week's prices: {s['capture_ratio']:.0%} of the "
            f"{_money(perfect)} perfect foresight allows"
        )
    else:
        how = "with perfect foresight of prices, an upper bound"
    text = (
        f"{battery} {where} {verb} about <strong>{_money(total)} a year</strong> "
        f"({_money(s['revenue_per_mw_year'])} per MW), {how}. "
        f"It cycles {s['cycles_per_day']:.1f} times a day on average."
    )
    if s["response_share"] > 0:
        text += f" {s['response_share']:.0%} of the revenue comes from frequency response."
    return text


def fragment(result: Result, power_mw: float) -> str:
    """The result block: answer, key numbers, charts, assumptions, downloads and sources."""
    r, s = result.request, result.summary
    params = html.escape(query(r, power_mw))
    numbers = [
        ("Revenue per MW-year", _money(s["revenue_per_mw_year"])),
        ("Perfect foresight per MW-year", _money(s["perfect_per_mw_year"])),
        ("Share of perfect foresight", f"{s['capture_ratio']:.0%}"),
        ("Cycles per day", f"{s['cycles_per_day']:.2f}"),
        ("Average spread captured", f"£{s['captured_spread']:.2f}/MWh"),
        ("Days simulated", f"{s['days']:.0f}"),
    ]
    cards = "".join(
        f'<div class="card"><div class="value">{value}</div><div>{name}</div></div>'
        for name, value in numbers
    )
    daily = result.daily.set_axis(pd.to_datetime(result.daily.index)) * power_mw
    charts = [
        figures.cumulative_revenue(
            {"this plan": daily["revenue"], "perfect foresight": daily["benchmark_revenue"]}
        ),
        figures.monthly_revenue(daily["revenue"]),
    ]
    plots = "".join(_plot(fig) for fig in charts)
    assumptions = "".join(f"<li>{html.escape(item)}</li>" for item in _assumptions(r, s))
    return (
        f'<p class="answer">{answer(result, power_mw)}</p>'
        f'<div class="cards">{cards}</div>{plots}'
        f"<details open><summary>What this assumes</summary><ul>{assumptions}</ul></details>"
        '<p class="actions">'
        f'<a href="/download/daily.csv?{params}">Daily revenue (CSV)</a>'
        f'<a href="/download/scenario.yaml?{params}">Scenario to run yourself (YAML)</a>'
        f'<a href="/battery?{params}">Full hourly report (runs now, 15 to 45 s)</a></p>'
        f'<p class="source">{html.escape(_sources(r))}</p>'
    )


def daily_csv(result: Result, power_mw: float) -> str:
    frame = (result.daily * power_mw).round(2)
    frame.columns = ["revenue_gbp", "perfect_foresight_revenue_gbp"]
    header = f"# {result.request.label}, {power_mw:g} MW. {_sources(result.request)}\n"
    return header + frame.to_csv(index_label="date")


def scenario_yaml(request: Request, power_mw: float) -> str:
    """A scenario that reproduces the result with the command line, from the repo root."""
    battery = {"power_mw": power_mw, "energy_mwh": power_mw * request.hours}
    dispatch = {"degradation_cost": DEGRADATION_COST}
    if request.source == "history":
        raw: dict[str, object] = {
            "name": f"app-gb-{request.year}",
            "data": {
                "source": "ember",
                "path": "data/prices/gb_day_ahead_ember.csv",
                "start": f"{request.year}-01-01",
                "end": f"{request.year}-12-31",
            },
            "battery": battery,
            "forecast": request.forecast,
            "dispatch": dispatch,
        }
        if request.services != "none":
            raw["response"] = {
                "path": "data/response/gb_dynamic_response.csv",
                "services": SERVICES[request.services],
            }
        command = "uv run openenergy run"
    else:
        raw = {
            "name": f"app-{str(request.pathway).lower().replace(' ', '-')}-{request.year}",
            "system": {
                "data": "data/system",
                "year": WEATHER_YEAR,
                "interconnectors": "links",
                "fes": {"pathway": request.pathway, "year": request.year},
            },
            "battery": battery,
            "forecast": request.forecast,
            "dispatch": dispatch,
        }
        command = "uv sync --extra system && uv run openenergy system run"
    head = (
        f"# {request.label}, from the OpenEnergy web app.\n"
        f"# Save in the OpenEnergy folder as app.yaml and run: {command} app.yaml\n"
    )
    return head + yaml.safe_dump(raw, sort_keys=False)


def _assumptions(request: Request, summary: dict[str, float]) -> list[str]:
    items = [
        "A price taker: the battery's trades do not move prices.",
        "Each day is planned at noon the day before, then settled at the prices that cleared.",
        f"95% efficiency each way, a £{DEGRADATION_COST:g}/MWh wear cost, no capacity fade.",
        "Revenue scales with power at a fixed duration, so results are per MW times your MW.",
    ]
    if request.services != "none":
        items.append(
            "Frequency response: every MW offered is accepted at the clearing price, delivery "
            "is always available and never penalised, and the energy it moves is not paid."
        )
    if request.source == "scenario":
        items.append(
            f"Prices are OpenEnergy's model of GB with this pathway's fleet and demand on "
            f"{WEATHER_YEAR}'s weather and fuel, carbon and neighbouring prices: not a "
            f"forecast. Modelled daily spreads are about {MODEL_SPREAD_SHARE:.0%} of real ones, "
            "so values are lower than on real prices."
        )
    if summary["days"] < 365:
        why = ""
        if request.source == "scenario" and request.forecast == "naive_last_week":
            why = " (the first week has no last week to plan on)"
        elif request.services == "dc_dm" and request.year == 2022:
            why = " (Dynamic Moderation starts on 26 March 2022)"
        items.append(f"{summary['days']:.0f} days simulated{why}, scaled to a year.")
    return items


def _sources(request: Request) -> str:
    if request.source == "scenario":
        return f"Prices modelled by OpenEnergy from open data. {SCENARIO_ATTRIBUTION}"
    text = EMBER_ATTRIBUTION
    if request.services != "none":
        text += " " + RESPONSE_ATTRIBUTION
    return text


def _plot(fig: go.Figure) -> str:
    return str(
        fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            default_width="100%",
            config={"displaylogo": False, "responsive": True},
        )
    )


def _money(value: float) -> str:
    """Pounds to three significant figures, e.g. £29,000 or £6,300."""
    if value == 0 or not math.isfinite(value):
        return "£0"
    magnitude = math.floor(math.log10(abs(value)))
    return f"£{round(value, 2 - magnitude):,.0f}"
