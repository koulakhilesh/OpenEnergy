"""Command-line interface: ``openenergy run | compare | data info``."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer

import openenergy
from openenergy.data.opsd import OPSDCsvSource
from openenergy.errors import ConfigError, OpenEnergyError
from openenergy.metrics.capture import capture_by_year
from openenergy.scenario import ScenarioRun, load_scenario, run_scenario, write_outputs
from openenergy.system.netload import load_system, net_load, netload_by_year, surplus
from openenergy.system.storage import sizing_grid

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
    typer.echo(_format_run(result))
    typer.echo(f"  {'outputs':<22}{destination}")


@app.command()
def compare(
    scenarios: Annotated[list[Path], typer.Argument(help="Scenario YAML files.")],
) -> None:
    """Run several scenarios and rank them by revenue (including any premium)."""
    with _reported_errors():
        rows = [(s.name, run_scenario(s).summary) for s in map(load_scenario, scenarios)]
    rows.sort(key=lambda row: row[1].total, reverse=True)
    name_width = max(len("scenario"), *(len(name) for name, _ in rows)) + 2
    forecast_width = max(len("forecast"), *(len(s.forecaster) for _, s in rows)) + 2
    header = f"{'scenario':<{name_width}}{'forecast':<{forecast_width}}"
    typer.echo(header + f"{'days':>6}{'revenue':>14}{'per MW-yr':>12}{'capture':>10}{'cycles':>9}")
    for name, s in rows:
        per_mw = "n/a" if s.revenue_per_mw_year is None else f"{s.revenue_per_mw_year:,.0f}"
        typer.echo(
            f"{name:<{name_width}}{s.forecaster:<{forecast_width}}{s.days:>6}{s.total:>14,.0f}"
            f"{per_mw:>12}{_percent(s.capture_ratio):>10}{s.equivalent_cycles:>9.0f}"
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


@app.command()
def netload(
    path: Annotated[Path, typer.Argument(help="OPSD time-series CSV.")],
    zone: Annotated[str, typer.Option("--zone", "-z", help="Bidding zone.")] = "GB_GBN",
    scale_wind: Annotated[float, typer.Option(help="Multiply wind output by this.")] = 1.0,
    scale_solar: Annotated[float, typer.Option(help="Multiply solar output by this.")] = 1.0,
    must_run: Annotated[float, typer.Option(help="Must-run floor in MW.")] = 0.0,
) -> None:
    """Net load, ramps and renewable surplus per year, optionally with renewables scaled."""
    with _reported_errors():
        system = load_system(OPSDCsvSource(path), zone)
        rows = netload_by_year(system.frame, scale_wind, scale_solar, must_run)
    typer.echo(
        f"net load for {zone}: wind x{scale_wind:g}, solar x{scale_solar:g}, "
        f"must-run {must_run:,.0f} MW (GW unless stated; "
        f"{system.load_flagged} load glitches removed)"
    )
    typer.echo(
        f"{'year':<6}{'RE share':>9}{'mean':>7}{'peak':>7}{'min':>7}{'ramp1h':>8}{'ramp3h':>8}"
        f"{'surplus TWh':>12}{'hours':>7}{'of RE':>7}{'GBP/MWh per GW':>16}"
    )
    for s in rows:
        slope = "n/a" if s.price_slope_per_gw is None else f"{s.price_slope_per_gw:.2f}"
        typer.echo(
            f"{s.year:<6}{s.renewable_share:>9.1%}{s.mean_net_mw / 1e3:>7.1f}"
            f"{s.peak_net_mw / 1e3:>7.1f}{s.min_net_mw / 1e3:>7.1f}"
            f"{s.ramp_1h_p99_mw / 1e3:>8.1f}{s.ramp_3h_p99_mw / 1e3:>8.1f}"
            f"{s.surplus_mwh / 1e6:>12.2f}{s.surplus_hours:>7}{s.surplus_share:>7.1%}{slope:>16}"
        )
    typer.echo("ramps are 99th percentiles of absolute hourly and 3-hour changes")


@app.command()
def storage(
    path: Annotated[Path, typer.Argument(help="OPSD time-series CSV.")],
    zone: Annotated[str, typer.Option("--zone", "-z", help="Bidding zone.")] = "GB_GBN",
    scale_wind: Annotated[float, typer.Option(help="Multiply wind output by this.")] = 1.0,
    scale_solar: Annotated[float, typer.Option(help="Multiply solar output by this.")] = 1.0,
    must_run: Annotated[float, typer.Option(help="Must-run floor in MW.")] = 0.0,
    power: Annotated[str, typer.Option(help="Fleet powers in MW, comma-separated.")] = (
        "1000,5000,10000,20000"
    ),
    hours: Annotated[str, typer.Option(help="Durations in hours, comma-separated.")] = ("2,4,8,24"),
) -> None:
    """Share of renewable surplus absorbed by storage fleets of each power and duration."""
    with _reported_errors():
        powers, durations = _floats(power, "power"), _floats(hours, "hours")
        system = load_system(OPSDCsvSource(path), zone)
        net = net_load(system.frame, scale_wind, scale_solar)
        grid = sizing_grid(net, powers, durations, must_run_mw=must_run)
    total = float(surplus(net, must_run).sum())
    typer.echo(
        f"surplus absorbed: wind x{scale_wind:g}, solar x{scale_solar:g}, "
        f"must-run {must_run:,.0f} MW, surplus {total / 1e6:,.2f} TWh over the data"
    )
    table = grid.pivot(index="power_mw", columns="hours", values="absorbed_share")
    typer.echo(f"{'GW':>8}" + "".join(f"{f'{h:g}h':>9}" for h in table.columns))
    for power_mw in table.index:
        shares = "".join(f"{share:>9.1%}" for share in table.loc[power_mw])
        typer.echo(f"{power_mw / 1e3:>8.1f}{shares}")


def _floats(text: str, name: str) -> list[float]:
    try:
        values = [float(part) for part in text.split(",") if part.strip()]
    except ValueError as exc:
        raise ConfigError(f"--{name} must be comma-separated numbers, got {text!r}") from exc
    if not values:
        raise ConfigError(f"--{name} needs at least one value")
    return values


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


def _format_run(run: ScenarioRun) -> str:
    s, money = run.summary, run.summary.currency
    lines = [
        f"{run.scenario.name} ({s.forecaster}, {money})",
        f"days simulated        {s.days} ({s.skipped_days} skipped)",
        f"revenue               {s.revenue:,.2f} {money}",
    ]
    if s.revenue_per_mw_year is not None:
        spread = "n/a" if s.captured_spread is None else f"{s.captured_spread:,.2f} {money}/MWh"
        lines += [
            f"revenue per MW-year   {s.revenue_per_mw_year:,.2f} {money}",
            f"captured spread       {spread}",
        ]
    if s.premium is not None and s.available_mwh is not None and s.curtailed_mwh is not None:
        curtailed = s.curtailed_mwh / s.available_mwh if s.available_mwh > 0 else None
        lines += [
            f"premium               {s.premium:,.2f} {money}",
            f"plant output          {s.available_mwh:,.0f} MWh ({_percent(curtailed)} curtailed)",
        ]
    lines += [
        f"equivalent cycles     {s.equivalent_cycles:,.1f}",
        f"final SOH             {s.final_soh:.4f}",
        f"forecast MAE / RMSE   {s.forecast_mae:,.2f} / {s.forecast_rmse:,.2f} {money}/MWh",
        f"capture ratio         {_percent(s.capture_ratio)}",
    ]
    if run.plant_capture is not None:
        p = run.plant_capture
        lines.append(
            f"plant captured price  {_number(p.captured_price)} {money}/MWh "
            f"({_percent(p.capture_rate)} of baseload)"
        )
    if run.colocation is not None:
        c = run.colocation
        lines += [
            f"separate assets       {c.plant_alone + c.battery_alone:,.2f} {money} "
            f"(plant {c.plant_alone:,.0f} + battery {c.battery_alone:,.0f})",
            f"co-location value     {c.value:,.2f} {money} (upper bound: plant output known)",
        ]
    return "\n  ".join(lines)


def _percent(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{digits}%}"


def _number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"
