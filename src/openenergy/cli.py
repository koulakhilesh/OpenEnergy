"""Command-line interface: ``openenergy run | compare | data info``."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer

import openenergy
from openenergy.data.opsd import OPSDCsvSource
from openenergy.errors import OpenEnergyError
from openenergy.metrics.capture import capture_by_year
from openenergy.metrics.summary import Summary
from openenergy.scenario import load_scenario, run_scenario, write_outputs

app = typer.Typer(no_args_is_help=True, add_completion=False, help=__doc__)
data_app = typer.Typer(no_args_is_help=True, help="Inspect market data files.")
app.add_typer(data_app, name="data")


@contextmanager
def _reported_errors() -> Iterator[None]:
    try:
        yield
    except OpenEnergyError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"openenergy {openenergy.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_show_version, is_eager=True, help="Show version."),
    ] = False,
) -> None:
    """Backtest battery storage against real power-market prices."""


@app.command()
def run(
    scenario: Annotated[Path, typer.Argument(help="Scenario YAML file.")],
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Output directory.")] = None,
) -> None:
    """Run one scenario, print its summary and write results."""
    with _reported_errors():
        loaded = load_scenario(scenario)
        result = run_scenario(loaded)
        destination = write_outputs(result, out or Path("outputs") / loaded.name)
    typer.echo(_format_summary(loaded.name, result.summary))
    typer.echo(f"  {'outputs':<22}{destination}")


@app.command()
def compare(
    scenarios: Annotated[list[Path], typer.Argument(help="Scenario YAML files.")],
) -> None:
    """Run several scenarios and rank them by revenue."""
    with _reported_errors():
        rows = [(s.name, run_scenario(s).summary) for s in map(load_scenario, scenarios)]
    rows.sort(key=lambda row: row[1].revenue, reverse=True)
    name_width = max(len("scenario"), *(len(name) for name, _ in rows)) + 2
    forecast_width = max(len("forecast"), *(len(s.forecaster) for _, s in rows)) + 2
    header = f"{'scenario':<{name_width}}{'forecast':<{forecast_width}}"
    typer.echo(header + f"{'days':>6}{'revenue':>14}{'per MW-yr':>12}{'capture':>10}{'cycles':>9}")
    for name, s in rows:
        typer.echo(
            f"{name:<{name_width}}{s.forecaster:<{forecast_width}}{s.days:>6}{s.revenue:>14,.0f}"
            f"{s.revenue_per_mw_year:>12,.0f}{_percent(s.capture_ratio):>10}"
            f"{s.equivalent_cycles:>9.0f}"
        )


@app.command()
def capture(
    path: Annotated[Path, typer.Argument(help="OPSD time-series CSV.")],
    zone: Annotated[str, typer.Option("--zone", "-z", help="Bidding zone.")] = "GB_GBN",
    technology: Annotated[
        list[str] | None,
        typer.Option("--technology", "-t", help="Technology (repeatable); default all."),
    ] = None,
) -> None:
    """Captured price and capture rate per year for each renewable technology."""
    with _reported_errors():
        source = OPSDCsvSource(path)
        prices = source.prices(zone)
        rows = [
            (tech, metrics)
            for tech in technology or source.technologies(zone)
            for metrics in capture_by_year(prices, source.profile(zone, tech))
        ]
    unit = f"{prices.currency}/MWh"
    typer.echo(
        f"{'year':<6}{'technology':<16}{'CF':>7}{'baseload':>11}{'captured':>11}"
        f"{'capture':>9}{'neg-price':>11}   (prices in {unit})"
    )
    for tech, m in rows:
        typer.echo(
            f"{m.label:<6}{tech:<16}{m.capacity_factor:>7.1%}{m.baseload_price:>11.2f}"
            f"{_number(m.captured_price):>11}{_percent(m.capture_rate):>9}"
            f"{_percent(m.negative_price_share, digits=2):>11}"
        )


@data_app.command("info")
def data_info(path: Annotated[Path, typer.Argument(help="OPSD time-series CSV.")]) -> None:
    """List price zones with currency, date range and data completeness."""
    with _reported_errors():
        source = OPSDCsvSource(path)
        for zone in source.zones():
            series = source.prices(zone)
            index = series.prices.index
            first, last = index[0].date(), index[-1].date()
            total = (last - first).days + 1
            complete = len(series.complete_days())
            typer.echo(
                f"{zone:<10}{series.currency:<5}{first} to {last}  {complete}/{total} complete days"
            )


def _format_summary(name: str, s: Summary) -> str:
    money = s.currency
    spread = "n/a" if s.captured_spread is None else f"{s.captured_spread:,.2f} {money}/MWh"
    lines = [
        f"{name} ({s.forecaster}, {money})",
        f"days simulated        {s.days} ({s.skipped_days} skipped)",
        f"revenue               {s.revenue:,.2f} {money}",
        f"revenue per MW-year   {s.revenue_per_mw_year:,.2f} {money}",
        f"captured spread       {spread}",
        f"equivalent cycles     {s.equivalent_cycles:,.1f}",
        f"final SOH             {s.final_soh:.4f}",
        f"forecast MAE / RMSE   {s.forecast_mae:,.2f} / {s.forecast_rmse:,.2f} {money}/MWh",
        f"capture ratio         {_percent(s.capture_ratio)}",
    ]
    return "\n  ".join(lines)


def _percent(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{digits}%}"


def _number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"
