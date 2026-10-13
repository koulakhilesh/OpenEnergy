"""Chart functions: pandas in, plotly figure out (no file I/O, reusable in an app)."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
import plotly.graph_objects as go

TEMPLATE = "plotly_white"
# Fuel colours, roughly following common GB grid dashboards.
TECH_COLOURS = {
    "nuclear": "#7b5ea7", "biomass": "#4f8f3a", "hydro": "#2b7bba", "wind": "#5ec3e6",
    "solar": "#f4c542", "imports": "#a0a0a0", "pumped_storage": "#1f4e79", "other": "#c9c9c9",
    "ccgt": "#e8743b", "coal": "#4d4d4d", "peaking": "#d62728", "unserved": "#000000",
}  # fmt: skip
TECH_ORDER = list(TECH_COLOURS)


def _times(frame: pd.Series | pd.DataFrame) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(frame.index)


def _months(index: pd.DatetimeIndex) -> pd.Index:
    """Calendar month labels (YYYY-MM), from naive or UTC timestamps."""
    naive = index.tz_convert(None) if index.tz is not None else index
    return naive.to_period("M").astype(str)


def _layout(fig: go.Figure, title: str, x: str, y: str) -> go.Figure:
    fig.update_layout(
        title=title,
        template=TEMPLATE,
        xaxis_title=x,
        yaxis_title=y,
        legend={"orientation": "h", "y": -0.2},
        margin={"l": 60, "r": 20, "t": 50, "b": 40},
        height=380,
    )
    return fig


def cumulative_revenue(
    runs: Mapping[str, pd.Series], currency: str = "GBP", title: str = "Cumulative revenue"
) -> go.Figure:
    """One line per named daily revenue series, summed over time."""
    fig = go.Figure()
    for name, daily in runs.items():
        fig.add_trace(go.Scatter(x=daily.index, y=daily.cumsum(), mode="lines", name=name))
    return _layout(fig, title, "Date", f"Revenue ({currency})")


def monthly_revenue(daily: pd.Series, currency: str = "GBP") -> go.Figure:
    monthly = daily.groupby(_months(_times(daily))).sum()
    fig = go.Figure(go.Bar(x=monthly.index, y=monthly.to_numpy(), name="revenue"))
    return _layout(fig, "Revenue by month", "Month", f"Revenue ({currency})")


def revenue_by_market(daily: pd.DataFrame, currency: str = "GBP") -> go.Figure:
    """Monthly trading and frequency-response revenue, stacked."""
    months = _months(_times(daily))
    fig = go.Figure()
    for column, label in (
        ("energy_revenue", "trading"),
        ("response_revenue", "frequency response"),
    ):
        monthly = daily[column].groupby(months).sum()
        fig.add_trace(go.Bar(x=monthly.index, y=monthly.to_numpy(), name=label))
    fig.update_layout(barmode="relative")
    return _layout(fig, "Revenue by market", "Month", f"Revenue ({currency})")


def typical_day(intervals: pd.DataFrame) -> go.Figure:
    """Mean charge and discharge (MW) by hour of day."""
    hour = _times(intervals).hour
    fig = go.Figure()
    for column, sign in (("discharge_mw", 1.0), ("charge_mw", -1.0)):
        mean = intervals[column].groupby(hour).mean() * sign
        fig.add_trace(go.Bar(x=mean.index, y=mean.to_numpy(), name=column.removesuffix("_mw")))
    fig.update_layout(barmode="relative")
    return _layout(fig, "Average day: discharge (+) and charge (-)", "Hour (UTC)", "MW")


def state_of_charge(intervals: pd.DataFrame) -> go.Figure:
    """Stored energy at the end of each interval, as a day by hour heat map."""
    energy = intervals["energy_mwh"]
    times = _times(energy)
    grid = energy.groupby([times.normalize(), times.hour]).mean().unstack()
    fig = go.Figure(
        go.Heatmap(
            x=grid.columns,
            y=grid.index,
            z=grid.to_numpy(),
            colorscale="Viridis",
            colorbar={"title": "MWh"},
        )
    )
    fig.update_layout(height=480)
    return _layout(fig, "Stored energy", "Hour (UTC)", "Day")


def price_and_forecast(intervals: pd.DataFrame, currency: str = "GBP") -> go.Figure:
    fig = go.Figure()
    for column in ("price", "forecast"):
        fig.add_trace(
            go.Scattergl(x=intervals.index, y=intervals[column], mode="lines", name=column)
        )
    fig.update_xaxes(rangeslider={"visible": True})
    return _layout(fig, "Actual price and the forecast planned on", "Time (UTC)", f"{currency}/MWh")


def forecast_error_by_hour(intervals: pd.DataFrame, currency: str = "GBP") -> go.Figure:
    error = (intervals["forecast"] - intervals["price"]).abs()
    mae = error.groupby(_times(intervals).hour).mean()
    fig = go.Figure(go.Bar(x=mae.index, y=mae.to_numpy(), name="mean absolute error"))
    return _layout(fig, "Forecast error by hour", "Hour (UTC)", f"{currency}/MWh")


def site_by_month(daily: pd.DataFrame) -> go.Figure:
    """Plant energy available and curtailed per month (co-located sites)."""
    months = _months(_times(daily))
    fig = go.Figure()
    for column, label in (("available_mwh", "available"), ("curtailed_mwh", "curtailed")):
        monthly = daily[column].groupby(months).sum()
        fig.add_trace(go.Bar(x=monthly.index, y=monthly.to_numpy(), name=label))
    fig.update_layout(barmode="group")
    return _layout(fig, "Plant output by month", "Month", "MWh")


def cumulative_emissions(daily: pd.Series) -> go.Figure:
    fig = go.Figure(go.Scatter(x=daily.index, y=daily.cumsum(), mode="lines", name="net"))
    return _layout(fig, "Net emissions (negative = avoided)", "Date", "tCO2")


def generation_by_month(dispatch: pd.DataFrame, step_hours: float = 1.0) -> go.Figure:
    """Stacked monthly generation (TWh) by technology."""
    months = _months(_times(dispatch))
    fig = go.Figure()
    for tech in [t for t in TECH_ORDER if t in dispatch.columns]:
        twh = dispatch[tech].groupby(months).sum() * step_hours / 1e6
        if (twh.abs() > 0).any():
            fig.add_trace(
                go.Bar(x=twh.index, y=twh.to_numpy(), name=tech, marker_color=TECH_COLOURS[tech])
            )
    fig.update_layout(barmode="relative")
    return _layout(fig, "Generation by month", "Month", "TWh")


def price_duration(series: Mapping[str, pd.Series], currency: str = "GBP") -> go.Figure:
    """Prices sorted from highest to lowest, one line per series, on a 0-100% axis."""
    fig = go.Figure()
    for name, values in series.items():
        ordered = np.sort(values.dropna().to_numpy())[::-1]
        share = np.linspace(0, 100, ordered.size)
        fig.add_trace(go.Scattergl(x=share, y=ordered, mode="lines", name=name))
    return _layout(fig, "Price duration curve", "Share of hours (%)", f"{currency}/MWh")


def mean_by(series: Mapping[str, pd.Series], by: str = "hour", currency: str = "GBP") -> go.Figure:
    """Mean of each series by hour of day or by month."""
    fig = go.Figure()
    for name, values in series.items():
        index = _times(values)
        key = index.hour if by == "hour" else _months(index)
        mean = values.groupby(key).mean()
        fig.add_trace(go.Scatter(x=mean.index, y=mean.to_numpy(), mode="lines+markers", name=name))
    label = "Hour (UTC)" if by == "hour" else "Month"
    return _layout(fig, f"Mean price by {by}", label, f"{currency}/MWh")


def system_by_month(dispatch: pd.DataFrame, step_hours: float = 1.0) -> go.Figure:
    """Curtailment (TWh) and fossil emissions (MtCO2) by month."""
    months = _months(_times(dispatch))
    curtailed = dispatch["curtailment"].groupby(months).sum() * step_hours / 1e6
    emissions = dispatch["emissions_t"].groupby(months).sum() / 1e6
    fig = go.Figure()
    fig.add_trace(go.Bar(x=curtailed.index, y=curtailed.to_numpy(), name="curtailed (TWh)"))
    fig.add_trace(
        go.Scatter(
            x=emissions.index,
            y=emissions.to_numpy(),
            name="emissions (MtCO2)",
            mode="lines+markers",
            yaxis="y2",
        )
    )
    fig.update_layout(yaxis2={"title": "MtCO2", "overlaying": "y", "side": "right"})
    return _layout(fig, "Curtailment and emissions by month", "Month", "TWh")


def model_vs_actual_by_year(years: pd.DataFrame, pairs: Mapping[str, str]) -> go.Figure:
    """Grouped bars of model and actual per year; ``pairs`` maps a label to a column stem."""
    fig = go.Figure()
    labels = years["year"].astype(str)
    for label, stem in pairs.items():
        for side in ("model", "actual"):
            column = f"{stem}_{side}"
            if column in years:
                fig.add_trace(go.Bar(x=labels, y=years[column], name=f"{label} {side}"))
    fig.update_layout(barmode="group")
    return _layout(fig, " and ".join(pairs) + ": model and actual by year", "Year", "")


def sweep_ranking(table: pd.DataFrame, keys: list[str], currency: str = "") -> go.Figure:
    labels = table[keys].astype(str).agg(", ".join, axis=1) if keys else table.index.astype(str)
    fig = go.Figure(go.Bar(x=table["total"], y=labels, orientation="h", name="total"))
    fig.update_layout(yaxis={"autorange": "reversed"}, height=max(300, 28 * len(table) + 120))
    return _layout(fig, "Sweep results, best first", f"Total {currency}".strip(), "")


def sweep_effect(table: pd.DataFrame, key: str) -> go.Figure:
    """Mean revenue per MW-year at each value of one swept setting."""
    mean = table.groupby(key)["revenue_per_mw_year"].mean().sort_index()
    fig = go.Figure(
        go.Scatter(x=mean.index.astype(str), y=mean.to_numpy(), mode="lines+markers", name=key)
    )
    return _layout(fig, f"Revenue per MW-year by {key}", key, "Revenue per MW-year")
