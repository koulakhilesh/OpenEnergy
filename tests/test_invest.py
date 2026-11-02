from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from openenergy import ConfigError
from openenergy.cli import app
from openenergy.invest import (
    Costs,
    appraise,
    battery_costs,
    capacity_market,
    irr,
    npv,
    revenue_cases,
)

ROOT = Path(__file__).parents[1]
DATA = ROOT / "data"


def test_npv_and_irr_agree() -> None:
    assert npv(100.0, 10.0, 10, 0.0) == pytest.approx(0.0)
    assert irr(100.0, 10.0, 10) == pytest.approx(0.0, abs=1e-9)
    rate = irr(1000.0, 150.0, 15)
    assert 0.12 < rate < 0.13
    assert npv(1000.0, 150.0, 15, rate) == pytest.approx(0.0, abs=1e-6)
    assert pd.isna(irr(1000.0, 50.0, 15))


def test_capacity_market_uses_the_latest_four_year_auction_with_a_factor(tmp_path: Path) -> None:
    pd.DataFrame(
        {
            "auction": ["A (T-4)", "B (T-4)", "C (T-4)", "D (T-1)"],
            "clearing_gbp_per_kw_year": [20.0, 60.0, 30.0, 5.0],
            "delivery_year": [2026, 2027, 2028, 2029],
            "type": ["T-4", "T-4", "T-4", "T-1"],
        }
    ).to_csv(tmp_path / "capacity_market_auctions.csv", index=False)
    pd.DataFrame(
        {
            "auction": ["A (T-4)", "B (T-4)", "D (T-1)"],
            "duration_hours": [2.0, 2.0, 2.0],
            "derating_factor": [0.3, 0.2, 0.25],
        }
    ).to_csv(tmp_path / "capacity_market_storage_derating.csv", index=False)
    market = capacity_market(tmp_path)
    assert market.auction == "B (T-4)"
    assert market.gbp_per_mw_year == pytest.approx(60.0 * 1000 * 0.2)
    assert capacity_market(tmp_path, price=10.0).gbp_per_mw_year == pytest.approx(2000.0)


def test_appraise_with_the_bundled_inputs() -> None:
    costs = battery_costs(DATA / "invest", 2025)
    assert battery_costs(DATA / "invest", 2025, 0.5).capex_gbp == pytest.approx(costs.capex_gbp / 2)
    with pytest.raises(ConfigError, match="no battery cost"):
        battery_costs(DATA / "invest", 1990)
    cases = revenue_cases(DATA)
    assert set(cases["family"]) >= {"Real batteries, energy and response"}
    table = appraise(cases, costs, capacity_market(DATA / "invest"), 15, 0.07)
    row = table.iloc[0]
    assert row["net"] == pytest.approx(row["revenue"] + row["capacity_market"] + row["fixed_om"])
    assert row["npv"] == pytest.approx(npv(costs.capex_gbp, row["net"], 15, 0.07))
    paying = Costs(2025, 0.5 * row["breakeven_capex"], costs.fixed_om_gbp_per_year)
    assert (
        appraise(cases.iloc[:1], paying, capacity_market(DATA / "invest"), 15, 0.07)["irr"].iloc[0]
        > 0.07
    )
    with pytest.raises(ConfigError, match="life"):
        appraise(cases, costs, capacity_market(DATA / "invest"), 0, 0.07)


def test_cli(tmp_path: Path) -> None:
    out = tmp_path / "invest.csv"
    result = CliRunner().invoke(app, ["invest", "--data", str(DATA), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert "break-even build cost" in result.output
    assert len(pd.read_csv(out)) == len(revenue_cases(DATA))
    bad = CliRunner().invoke(app, ["invest", "--data", str(DATA), "--cost-scale", "0"])
    assert bad.exit_code == 1
