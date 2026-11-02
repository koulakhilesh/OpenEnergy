"""The headline numbers in the docs, recomputed from the bundled outputs they come from.

A number that drifts from its source fails here, so the docs cannot quietly go stale when a
study is re-run. Each check names the file it reads and the pages that quote it.
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parents[1]
DOCS = ROOT / "docs"


def page(name: str) -> str:
    return (DOCS / name).read_text()


def pounds(value: float) -> str:
    return f"{value:,.0f}"


@pytest.fixture(scope="module")
def saturation() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data/scenarios/saturation.csv")


def test_saturation_falling_behind(saturation: pd.DataFrame) -> None:
    rows = saturation[saturation["pathway"] == "Falling Behind"].sort_values("battery_scale")
    values = [pounds(v) for v in rows["revenue_per_mw_year"]]
    assert f"| Falling Behind: one more battery earns | {' | '.join(values)} |" in page(
        "guides/forward-scenarios.md"
    )
    by_scale = dict(zip(rows["battery_scale"], values, strict=True))
    assert f"£{by_scale[1.0]} against £{by_scale[0.0]} per MW-year" in page("findings.md")


def test_saturation_firm_capacity_replaced(saturation: pd.DataFrame) -> None:
    with_fleet = saturation[saturation["battery_scale"] == 1.0]
    # "In the pathways that need it": those still short of firm capacity with the FES fleet.
    firm = with_fleet.loc[with_fleet["firm_added_mw"] > 0, "equivalent_firm"]
    quoted = f"{firm.min():.2f}–{firm.max():.2f} MW"  # noqa: RUF001 (the docs' en dash)
    for name in ("findings.md", "whats-new.md"):
        assert quoted in page(name), name


def test_scotland_transfer_table() -> None:
    demand = pd.read_csv(ROOT / "data/zones/demand_by_zone.csv")
    demand["year"] = demand["utc_timestamp"].str[:4].astype(int)
    text = page("guides/constraints.md")
    for year, rows in demand.dropna(subset=["scottish_transfer_mw"]).groupby("year"):
        flow = rows["scottish_transfer_mw"]
        cells = [
            f"{rows['scotland_demand_mw'].mean() / 1000:.2f}",
            f"{flow.mean() / 1000:.2f}",
            f"{flow.quantile(0.95) / 1000:.2f} / {flow.max() / 1000:.2f}",
            f"{(flow > 0).mean():.0%}",
            f"{flow.clip(lower=0).sum() * 0.5 / 1e6:.1f}",
        ]
        assert f" | {' | '.join(cells)} |" in text, year


def test_real_batteries_tables() -> None:
    text = page("guides/real-batteries.md")

    def gbp(value: float) -> str:
        return f"£{value:,.0f}" if value >= 0 else f"−£{-value:,.0f}"  # noqa: RUF001 (minus sign)

    years = pd.read_csv(ROOT / "data/fleet/real_vs_model.csv").set_index("year")
    for year in (2023, 2024, 2025):
        r = years.loc[year]
        cells = [
            str(int(r["units"])),
            f"{r['mw_years']:,.0f} ({r['repd_battery_mw']:,.0f})",
            f"{r['discharge_hours']:.0f}",
            gbp(r["real_metered_day_ahead_per_mw_year"]),
            gbp(r["real_estimated_total_per_mw_year"]),
            gbp(r["real_response_per_mw_year"]),
            gbp(r["real_total_with_response_per_mw_year"]),
            " / ".join(
                gbp(r[f"model_1h_{n}_per_mw_year"]) for n in ("naive", "fundamentals", "perfect")
            ),
            gbp(r["model_2h_perfect_per_mw_year"]),
        ]
        assert f"| {year} | {' | '.join(cells)} |" in text, year
    zones = pd.read_csv(ROOT / "data/fleet/real_by_zone.csv").set_index(["year", "zone"])
    names = {"scotland": "Scotland", "england_wales": "England and Wales"}
    for (year, zone), r in zones.loc[[2024, 2025]].iterrows():
        values = [
            "estimated_total",
            "response",
            "estimated_total_with_response",
            "pn_value_day_ahead",
            "bm_net",
            "imbalance",
            "metered_value_day_ahead",
        ]
        cells = [str(int(r["units"])), *(gbp(r[f"{v}_per_mw_year"]) for v in values)]
        assert f"| {year} | {names[zone]} | {' | '.join(cells)} |" in text, (year, zone)


def test_investment_table() -> None:
    from openenergy.invest import summary

    text = page("guides/investment.md")
    table = summary(pd.read_csv(ROOT / "data/invest/cases.csv"))
    for family, r in table.iterrows():
        breakeven = " / ".join(
            f"{v:,.0f}" if v >= 0 else f"−{-v:,.0f}"  # noqa: RUF001 (minus sign)
            for v in (r["breakeven_min"], r["breakeven_median"], r["breakeven_max"])
        )
        cells = [
            str(int(r["cases"])),
            f"{r['revenue_median']:,.0f}",
            breakeven,
            str(int(r["worth_building"])),
        ]
        assert f"| {family} | {' | '.join(cells)} |" in text, family


def test_two_zones_table() -> None:
    text = page("guides/constraints.md")
    years = pd.read_csv(ROOT / "data/zones/two_zones_by_year.csv")
    for r in years.itertuples():
        cells = [
            f"{r.limit_mw / 1000:.2f}",
            f"{r.transfer_mean_model / 1000:.2f} / {r.transfer_mean_actual / 1000:.2f}",
            f"{r.correlation:.2f}",
            f"{r.model_at_limit_share:.0%}",
            f"{r.price_split_share:.0%}",
            f"{r.price_gap_mean:.1f}",
            f"{r.battery_scotland:,.0f}",
        ]
        assert f"| {r.year} | {' | '.join(cells)} |" in text, r.year


def test_live_lag_table() -> None:
    text = page("guides/research.md")
    mean = pd.read_csv(ROOT / "data/forecasts/live_lag_2025.csv").drop(columns="date").mean()
    rows = {
        "The auction (backtest)": "mae_auction",
        "2 days before": "mae_lag_2d",
        "3 days before": "mae_lag_3d",
        "4 days before": "mae_lag_4d",
        "Last week's prices": "mae_last_week",
    }
    for name, column in rows.items():
        assert f"| {name} | {mean[column]:.2f} |" in text, name


def test_evening_premium_tables() -> None:
    text = page("guides/system-model.md")

    def num(value: float) -> str:
        return f"{value:.1f}" if value >= 0 else f"−{-value:.1f}"  # noqa: RUF001 (minus sign)

    margins = pd.read_csv(ROOT / "data/scarcity/evening_premium_by_margin.csv")
    for r in margins.itertuples():
        band = str(r.derated_margin_gw).replace("-", "–")  # noqa: RUF001 (the docs' en dash)
        cells = [f"{r.hours:,}", num(r.gap), num(r.gap_vs_day), num(r.scarcity)]
        assert f"| {band} | {' | '.join(cells)} |" in text, band
    years = pd.read_csv(ROOT / "data/scarcity/evening_premium_by_year.csv")
    for r in years[years["year"] >= 2019].itertuples():
        cells = [
            num(r.evening_gap_vs_day),
            num(r.evening_scarcity),
            f"{r.margin_correlation:.2f}",
            f"{r.mae_model:.1f} / {r.mae_with_scarcity:.1f}",
            f"{r.correlation_model:.2f} / {r.correlation_with_scarcity:.2f}",
        ]
        assert f"| {r.year} | {' | '.join(cells)} |" in text, r.year
