"""The app's wording and downloads: answer sentences, assumptions, sources, CSV and YAML."""

from __future__ import annotations

import math

import yaml

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

SERVICE_NAMES = {
    "dc": "Dynamic Containment",
    "dc_dm": "Dynamic Containment and Moderation",
}
MODEL_SPREAD_SHARE = 0.77  # modelled 2025 daily spread 52.0 / actual 67.5 (forward guide)
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
            f"{money(perfect)} perfect foresight allows"
        )
    else:
        how = "with perfect foresight of prices, an upper bound"
    text = (
        f"{battery} {where} {verb} about {money(total)} a year "
        f"({money(s['revenue_per_mw_year'])} per MW), {how}. "
        f"It cycles {s['cycles_per_day']:.1f} times a day on average."
    )
    if s["response_share"] > 0:
        text += f" {s['response_share']:.0%} of the revenue comes from frequency response."
    return text


def assumptions(request: Request, summary: dict[str, float]) -> list[str]:
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


def sources(request: Request) -> str:
    if request.source == "scenario":
        return f"Prices modelled by OpenEnergy from open data. {SCENARIO_ATTRIBUTION}"
    text = EMBER_ATTRIBUTION
    if request.services != "none":
        text += " " + RESPONSE_ATTRIBUTION
    return text


def daily_csv(result: Result, power_mw: float) -> str:
    frame = (result.daily * power_mw).round(2)
    frame.columns = ["revenue_gbp", "perfect_foresight_revenue_gbp"]
    header = f"# {result.request.label}, {power_mw:g} MW. {sources(result.request)}\n"
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
                "commitment": True,
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


def money(value: float) -> str:
    """Pounds to three significant figures, e.g. £29,000 or £6,300."""
    if value == 0 or not math.isfinite(value):
        return "£0"
    magnitude = math.floor(math.log10(abs(value)))
    return f"£{round(value, 2 - magnitude):,.0f}"
