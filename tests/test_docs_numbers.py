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
            "pn_value_day_ahead",
            "bm_net",
            "imbalance",
            "metered_value_day_ahead",
        ]
        cells = [str(int(r["units"])), *(gbp(r[f"{v}_per_mw_year"]) for v in values)]
        assert f"| {year} | {names[zone]} | {' | '.join(cells)} |" in text, (year, zone)
