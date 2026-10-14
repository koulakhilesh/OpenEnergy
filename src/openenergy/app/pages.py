"""HTML for the app's result page: the answer first, then charts, assumptions and downloads."""

from __future__ import annotations

import html
import math
from urllib.parse import urlencode

import pandas as pd
import plotly.graph_objects as go
import yaml
from plotly.offline import get_plotlyjs_version

from openenergy.app.results import PRECOMPUTED_HOURS, Result, Store
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
HELP = {
    "power": "The most the battery can charge or discharge at once. Revenue scales with it.",
    "duration": "Hours to fill or empty at full power: a 10 MW, 2-hour battery stores 20 MWh.",
    "forecast": (
        "Last week's prices: each day is planned as if prices repeat the same day last "
        "week, a simple forecast anyone could make. Perfect foresight: planned knowing "
        "every price, the most the battery could earn."
    ),
    "response": (
        "NESO pays batteries to hold power ready for when grid frequency drifts from 50 Hz: "
        "Dynamic Containment reacts within a second, Dynamic Moderation keeps frequency "
        "near 50 Hz. Auction prices exist from late 2021 (Moderation from March 2022)."
    ),
    "pathway": (
        "NESO's Future Energy Scenarios describe GB's power plants and demand to 2050. "
        "Prices here are OpenEnergy's model of that system on 2025's weather: not a forecast."
    ),
    "perfect": "What the same battery earns knowing every price in advance: an upper bound.",
    "share": "This plan's revenue as a share of perfect foresight on the same days.",
    "cycles": "Full charge-and-discharge cycles a day; more cycling wears a battery faster.",
    "spread": "Average price received when selling minus paid when buying, per MWh sold.",
}


def tip(name: str) -> str:
    """A focusable "?" that shows the explanation on hover, focus or tap."""
    text = html.escape(HELP[name])
    return (
        f'<span class="tip" tabindex="0" role="note" aria-label="{text}" data-tip="{text}">?</span>'
    )


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
        ("Revenue per MW-year", _money(s["revenue_per_mw_year"]), ""),
        ("Perfect foresight per MW-year", _money(s["perfect_per_mw_year"]), "perfect"),
        ("Share of perfect foresight", f"{s['capture_ratio']:.0%}", "share"),
        ("Cycles per day", f"{s['cycles_per_day']:.2f}", "cycles"),
        ("Average spread captured", f"£{s['captured_spread']:.2f}/MWh", "spread"),
        ("Days simulated", f"{s['days']:.0f}", ""),
    ]
    cards = "".join(
        f'<div class="card"><div class="value">{value}</div><div>{name} '
        f"{tip(help_key) if help_key else ''}</div></div>"
        for name, value, help_key in numbers
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
    more = ""
    if r.hours in PRECOMPUTED_HOURS:
        shared = {"hours": f"{r.hours:g}", "forecast": r.forecast, "power_mw": f"{power_mw:g}"}
        explore = urlencode({**shared, "services": r.services})
        compare = urlencode({**shared, "item": r.prices})
        more = (
            f'<a href="/explore?{html.escape(explore)}">Every year and pathway</a>'
            f'<a href="/compare?{html.escape(compare)}">Compare with others</a>'
        )
    return (
        f'<p class="answer">{answer(result, power_mw)}</p>'
        f'<div class="cards">{cards}</div>{plots}'
        f"<details open><summary>What this assumes</summary><ul>{assumptions}</ul></details>"
        f'<p class="actions">{more}'
        f'<a href="/download/daily.csv?{params}">Daily revenue (CSV)</a>'
        f'<a href="/download/scenario.yaml?{params}">Scenario to run yourself (YAML)</a>'
        f'<a href="/battery?{params}">Full hourly report (runs now, 15 to 45 s)</a></p>'
        f'<p class="source">{html.escape(_sources(r))}</p>'
    )


_CLICK = (
    "document.getElementById('{plot_id}').on('plotly_click', e => {"
    " const url = e.points[0].customdata; if (url) window.location.href = url; });"
)


def explore(store: Store, hours: float, forecast: str, services: str, power_mw: float) -> str:
    """Value by GB year and by FES pathway for one battery, each bar opening its result."""
    found = {r.key: store.get(r) for r in store.requests(hours, forecast)}
    results = [result for result in found.values() if result is not None]
    history = [
        x for x in results if x.request.source == "history" and x.request.services == services
    ]
    pathways = [x for x in results if x.request.source == "scenario"]
    years = _bars(
        [x.request.where for x in history],
        {"this plan": history}
        | ({"perfect foresight": history} if forecast == "naive_last_week" else {}),
        power_mw,
        "GB day-ahead prices by year",
    )
    by_target = {
        str(target): [x for x in pathways if x.request.year == target]
        for target in sorted({x.request.year for x in pathways})
    }
    names = [x.request.pathway or "" for x in next(iter(by_target.values()), [])]
    forward = _bars(names, by_target, power_mw, "FES pathways (modelled prices)")
    note = (
        "<p>Frequency response is available on historic years only, so pathways show "
        "trading alone.</p>"
        if services != "none"
        else ""
    )
    return (
        f"{years}{_table(history, power_mw)}<h2>FES pathways {tip('pathway')}</h2>{note}"
        f"{forward}{_table(pathways, power_mw)}"
    )


def compare(results: list[Result], power_mw: float) -> str:
    """Side by side: answer sentences, key numbers and revenue through the year."""
    if not results:
        return "<p>Choose up to three to compare.</p>"
    fig = go.Figure()
    for result in results:
        cumulative = (result.daily["revenue"] * power_mw).cumsum()
        fig.add_trace(
            go.Scatter(
                x=list(range(1, len(cumulative) + 1)),
                y=cumulative.to_numpy(),
                mode="lines",
                name=result.request.where,
            )
        )
    fig.update_layout(
        title="Revenue through the year (this plan)",
        template=figures.TEMPLATE,
        xaxis_title="Day simulated",
        yaxis_title="Revenue (GBP)",
        legend={"orientation": "h", "y": -0.2},
        margin={"l": 60, "r": 20, "t": 50, "b": 40},
        height=380,
    )
    answers = "".join(f'<p class="answer">{answer(x, power_mw)}</p>' for x in results)
    return f"{_table(results, power_mw)}{_plot(fig)}{answers}"


def _bars(labels: list[str], series: dict[str, list[Result]], power_mw: float, title: str) -> str:
    if not labels:
        return "<p>No precomputed results for this choice.</p>"
    fig = go.Figure()
    for name, items in series.items():
        field = "perfect_per_mw_year" if name == "perfect foresight" else "revenue_per_mw_year"
        fig.add_trace(
            go.Bar(
                x=labels,
                y=[x.summary[field] * power_mw for x in items],
                name=name,
                customdata=[f"/result?{query(x.request, power_mw)}" for x in items],
                hovertemplate="%{x}: £%{y:,.0f} a year<extra>" + name + "</extra>",
            )
        )
    fig.update_layout(
        title=f"{title} (click a bar to open it)",
        template=figures.TEMPLATE,
        yaxis_title=f"Revenue for {power_mw:g} MW (GBP a year)",
        barmode="group",
        legend={"orientation": "h", "y": -0.2},
        margin={"l": 60, "r": 20, "t": 50, "b": 40},
        height=380,
        showlegend=len(series) > 1,
    )
    return _plot(fig, post_script=_CLICK)


def _table(results: list[Result], power_mw: float) -> str:
    if not results:
        return ""
    header = (
        f"<tr><th>Prices</th><th>Revenue for {power_mw:g} MW</th><th>Per MW</th>"
        f"<th>Share of perfect foresight {tip('share')}</th>"
        f"<th>Cycles a day {tip('cycles')}</th><th></th></tr>"
    )
    rows = "".join(
        f"<tr><td>{html.escape(x.request.where)}</td>"
        f"<td>{_money(x.summary['revenue_per_mw_year'] * power_mw)}</td>"
        f"<td>{_money(x.summary['revenue_per_mw_year'])}</td>"
        f"<td>{x.summary['capture_ratio']:.0%}</td><td>{x.summary['cycles_per_day']:.1f}</td>"
        f'<td><a href="/result?{html.escape(query(x.request, power_mw))}">Open</a></td></tr>'
        for x in results
    )
    return f'<div class="wide"><table>{header}{rows}</table></div>'


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


def _plot(fig: go.Figure, post_script: str | None = None) -> str:
    return str(
        fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            default_width="100%",
            config={"displaylogo": False, "responsive": True},
            post_script=post_script,
        )
    )


def _money(value: float) -> str:
    """Pounds to three significant figures, e.g. £29,000 or £6,300."""
    if value == 0 or not math.isfinite(value):
        return "£0"
    magnitude = math.floor(math.log10(abs(value)))
    return f"£{round(value, 2 - magnitude):,.0f}"
