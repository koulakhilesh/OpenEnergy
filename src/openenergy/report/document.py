"""Assemble output directories into one HTML report."""

from __future__ import annotations

import html
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import plotly.graph_objects as go

import openenergy
from openenergy.report import figures
from openenergy.report.load import (
    BackcastOutput,
    BatteryOutput,
    Output,
    SweepOutput,
    SystemOutput,
)

LICENCE_NOTE = (
    "OpenEnergy code is MIT licensed and its documentation CC BY 4.0. Data keep their own "
    "licences; the attribution for each run is repeated in its section."
)
_STYLE = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1f2933}
header,main,footer{max-width:1100px;margin:0 auto;padding:0 24px}
header{padding-top:24px}h1{margin-bottom:4px}
h2{margin-top:40px;border-bottom:2px solid #e4e7eb}
.meta{color:#616e7c;font-size:14px}
table{border-collapse:collapse;margin:12px 0;font-size:14px}
th,td{border:1px solid #e4e7eb;padding:4px 10px;text-align:right}
th:first-child,td:first-child{text-align:left}th{background:#f5f7fa}
.note{background:#fffbea;border-left:4px solid #f0b429;padding:8px 12px;font-size:14px}
.source{color:#616e7c;font-size:12px;margin:8px 0}
footer{color:#616e7c;font-size:12px;padding:32px 24px}nav a{margin-right:12px}
.wide{overflow-x:auto}
"""


class _Figures:
    """Renders figures to HTML, putting plotly.js only in the first one."""

    def __init__(self, cdn: bool) -> None:
        self._library: bool | str = "cdn" if cdn else True

    def __call__(self, fig: go.Figure) -> str:
        library, self._library = self._library, False
        return str(
            fig.to_html(
                full_html=False,
                include_plotlyjs=library,
                default_width="100%",
                config={"displaylogo": False, "responsive": True},
            )
        )


def build_report(
    outputs: Sequence[Output], title: str = "OpenEnergy report", cdn: bool = False
) -> str:
    """One self-contained HTML document (plotly.js inlined unless ``cdn``)."""
    if not outputs:
        raise ValueError("no outputs to report")
    render = _Figures(cdn)
    sections: list[tuple[str, str]] = []
    batteries = [o for o in outputs if isinstance(o, BatteryOutput)]
    systems = [o for o in outputs if isinstance(o, SystemOutput)]
    if len(batteries) > 1:
        sections.append(("Battery comparison", _battery_comparison(batteries, render)))
    if len(systems) > 1:
        sections.append(("System comparison", _system_comparison(systems, render)))
    for output in outputs:
        sections.append((output.name, _section(output, render)))
    anchors = [f"s{i}" for i in range(len(sections))]
    nav = " ".join(
        f'<a href="#{a}">{_e(name)}</a>' for a, (name, _) in zip(anchors, sections, strict=True)
    )
    body = "\n".join(
        f'<section id="{a}"><h2>{_e(name)}</h2>{content}</section>'
        for a, (name, content) in zip(anchors, sections, strict=True)
    )
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_e(title)}</title><style>{_STYLE}</style></head><body>"
        f'<header><h1>{_e(title)}</h1><p class="meta">Generated {stamp} by OpenEnergy '
        f"{_e(openenergy.__version__)} from {len(outputs)} output(s).</p><nav>{nav}</nav>"
        f"</header><main>{body}</main><footer>{_e(LICENCE_NOTE)}</footer></body></html>\n"
    )


def _section(output: Output, render: Callable[[go.Figure], str]) -> str:
    if isinstance(output, BatteryOutput):
        return _battery(output, render)
    if isinstance(output, SystemOutput):
        return _system(output, render)
    if isinstance(output, BackcastOutput):
        return _backcast(output, render)
    return _sweep(output, render)


def _battery(run: BatteryOutput, render: Callable[[go.Figure], str]) -> str:
    s = run.summary.get("summary", {})
    money = str(s.get("currency", ""))
    rows = [
        ("Forecaster", s.get("forecaster")),
        ("Days simulated (skipped)", f"{s.get('days')} ({s.get('skipped_days')})"),
        (f"Revenue ({money})", _num(s.get("revenue"))),
        (f"Revenue per MW-year ({money})", _num(s.get("revenue_per_mw_year"))),
        ("Capture of perfect foresight", _pct(s.get("capture_ratio"))),
        (f"Captured spread ({money}/MWh)", _num(s.get("captured_spread"), 2)),
        ("Equivalent cycles", _num(s.get("equivalent_cycles"))),
        ("Final state of health", _pct(s.get("final_soh"))),
        (f"Forecast MAE ({money}/MWh)", _num(s.get("forecast_mae"), 2)),
    ]
    if s.get("premium") is not None:
        rows.append((f"Premium ({money})", _num(s.get("premium"))))
    if s.get("curtailed_mwh") is not None:
        rows.append(("Curtailed (MWh)", _num(s.get("curtailed_mwh"))))
    if s.get("emissions_t") is not None:
        rows.append(("Net emissions (tCO2)", _num(s.get("emissions_t"))))
    revenue = {"this run": run.daily["revenue"]}
    if run.benchmark_daily is not None:
        revenue["perfect foresight"] = run.benchmark_daily["revenue"]
    charts = [
        figures.cumulative_revenue(revenue, money),
        figures.monthly_revenue(run.daily["revenue"], money),
        figures.typical_day(run.intervals),
        figures.state_of_charge(run.intervals),
        figures.price_and_forecast(run.intervals, money),
        figures.forecast_error_by_hour(run.intervals, money),
    ]
    if "available_mwh" in run.daily:
        charts.append(figures.site_by_month(run.daily))
    if "emissions_t" in run.daily:
        charts.append(figures.cumulative_emissions(run.daily["emissions_t"]))
    notes = [run.summary.get("note"), run.summary.get("carbon_note")]
    sources = [run.summary.get("attribution"), run.summary.get("carbon_attribution")]
    return _block(rows, charts, render, notes, sources)


def _system(run: SystemOutput, render: Callable[[go.Figure], str]) -> str:
    s = run.summary.get("system", {})
    rows = [
        ("Year", s.get("year")),
        ("Price", s.get("price")),
        ("Mean price (GBP/MWh)", _num(s.get("price_mean"), 2)),
        ("Actual mean price (GBP/MWh)", _num(s.get("actual_price_mean"), 2)),
        ("Price p05 / p95", f"{_num(s.get('price_p05'), 1)} / {_num(s.get('price_p95'), 1)}"),
        ("Mean daily spread (GBP/MWh)", _num(s.get("daily_spread"), 1)),
        ("Curtailment (TWh)", _num(s.get("curtailment_twh"), 2)),
        ("Unserved (MWh)", _num(s.get("unserved_mwh"))),
        ("Fossil emissions (MtCO2)", _num(s.get("emissions_mt"), 2)),
        ("System cost (GBP m)", _num(s.get("cost_m"))),
        ("Solver", s.get("backend")),
    ]
    battery = run.summary.get("battery")
    if isinstance(battery, dict):
        rows.append(("Battery revenue per MW-year", _num(battery.get("revenue_per_mw_year"))))
        rows.append(("Battery capture", _pct(battery.get("capture_ratio"))))
    step = _step_hours(run.dispatch.index)
    price = {"model": run.dispatch["price"]}
    if "start_price" in run.dispatch:
        price["start price"] = run.dispatch["start_price"]
    charts = [
        figures.generation_by_month(run.dispatch, step),
        figures.price_duration(price),
        figures.mean_by(price, "hour"),
        figures.system_by_month(run.dispatch, step),
    ]
    return _block(rows, charts, render, [run.summary.get("note")], run.summary.get("attribution"))


def _backcast(run: BackcastOutput, render: Callable[[go.Figure], str]) -> str:
    columns = {
        "year": "Year", "hours": "Hours", "price_model": "Model GBP/MWh",
        "price_actual": "Actual GBP/MWh", "mae": "MAE", "correlation": "Corr.",
        "p95_model": "p95 model", "p95_actual": "p95 actual",
        "daily_spread_model": "Spread model", "daily_spread_actual": "Spread actual",
        "gas_twh_model": "Gas TWh model", "gas_twh_actual": "Gas TWh actual",
        "coal_twh_model": "Coal TWh model", "coal_twh_actual": "Coal TWh actual",
    }  # fmt: skip
    present = [c for c in columns if c in run.years]
    table = _table(
        [columns[c] for c in present],
        [[_cell(row[c]) for c in present] for row in run.years[present].to_dict("records")],
    )
    price = {"model": run.hourly["price_model"], "actual": run.hourly["price_actual"]}
    charts = [
        figures.mean_by(price, "hour"),
        figures.mean_by(price, "month"),
        figures.price_duration(price),
        figures.model_vs_actual_by_year(run.years, {"Gas TWh": "gas_twh", "Coal TWh": "coal_twh"}),
    ]
    kind = run.summary.get("price", "marginal")
    head = f'<p class="meta">Modelled price: {_e(kind)}.</p>{table}'
    notes = [run.summary.get("note")]
    return head + _block([], charts, render, notes, run.summary.get("attribution"))


def _sweep(run: SweepOutput, render: Callable[[go.Figure], str]) -> str:
    shown = [*run.keys, "total", "revenue_per_mw_year", "capture_ratio", "equivalent_cycles"]
    records = run.table[shown].to_dict("records")
    table = _table(shown, [[_cell(row[c]) for c in shown] for row in records])
    charts = [figures.sweep_ranking(run.table, run.keys)]
    charts += [figures.sweep_effect(run.table, key) for key in run.keys]
    return table + "".join(render(fig) for fig in charts)


def _battery_comparison(runs: list[BatteryOutput], render: Callable[[go.Figure], str]) -> str:
    labels = ["Revenue", "Revenue per MW-year", "Capture", "Cycles", "Final SOH"]
    keys = ["revenue", "revenue_per_mw_year", "capture_ratio", "equivalent_cycles", "final_soh"]
    rows = []
    for run in runs:
        s = run.summary.get("summary", {})
        values = [_pct(s.get(k)) if k in ("capture_ratio", "final_soh") else _num(s.get(k))
                  for k in keys]  # fmt: skip
        rows.append([run.name, *values])
    money = str(runs[0].summary.get("summary", {}).get("currency", ""))
    chart = figures.cumulative_revenue({r.name: r.daily["revenue"] for r in runs}, money)
    return _table(["Run", *labels], rows) + render(chart)


def _system_comparison(runs: list[SystemOutput], render: Callable[[go.Figure], str]) -> str:
    price = {r.name: r.dispatch["price"] for r in runs}
    return render(figures.price_duration(price)) + render(figures.mean_by(price, "hour"))


def _block(
    rows: list[tuple[str, Any]],
    charts: list[go.Figure],
    render: Callable[[go.Figure], str],
    notes: Sequence[Any],
    sources: Any,
) -> str:
    parts = (
        [_table(["", "Value"], [[label, _cell(value)] for label, value in rows])] if rows else []
    )
    parts += [f'<p class="note">{_e(note)}</p>' for note in notes if note]
    parts += [render(fig) for fig in charts]
    flat = sources if isinstance(sources, list) else [sources]
    parts += [f'<p class="source">Source: {_e(text)}</p>' for text in flat if text]
    return "\n".join(parts)


def _table(header: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    head = "".join(f"<th>{_e(h)}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in row) + "</tr>" for row in rows)
    table = f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    return f'<div class="wide">{table}</div>'


def _step_hours(index: pd.Index) -> float:
    stamps = pd.DatetimeIndex(index)
    return float((stamps[1] - stamps[0]) / pd.Timedelta(hours=1)) if len(stamps) > 1 else 1.0


def _cell(value: Any) -> str:
    if isinstance(value, float):
        return _num(value, 2 if abs(value) < 100 else 0)
    return "" if value is None else str(value)


def _num(value: Any, digits: int = 0) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    return f"{float(value):,.{digits}f}"


def _pct(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.1%}"


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))
