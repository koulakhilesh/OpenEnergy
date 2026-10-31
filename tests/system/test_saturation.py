from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from openenergy.cli import app
from openenergy.system.saturation import firm_from, saturation_study, saturation_summary

ROOT = Path(__file__).parents[2]


def test_saturation_on_a_cold_still_spell(tmp_path: Path) -> None:
    # 20-23 January 2025 only: the study's machinery on a few days, not a result.
    study = {
        "pathways": ["Holistic Transition"],
        "year": 2035,
        "scales": (0.0, 1.0),
        "weather_years": (2025,),
        "window": ("01-20", "01-23"),
    }
    rows = saturation_study(ROOT / "data/system", **study)  # type: ignore[arg-type]
    assert len(rows) == 2 and (rows["unserved_hours"] <= 3).all()
    assert (rows["scarcity_revenue"] <= rows["revenue_per_mw_year"] + 1e-9).all()
    assert (rows["scarcity_days"] <= 4).all()
    table = saturation_summary(rows).set_index("battery_scale")
    assert table.loc[0.0, "fleet_battery_mw"] == 0
    assert table.loc[1.0, "fleet_battery_mw"] > 0
    assert table.loc[0.0, "firm_added_mw"] >= table.loc[1.0, "firm_added_mw"] > 0
    assert table.loc[1.0, "equivalent_firm"] == pytest.approx(
        (table.loc[0.0, "firm_added_mw"] - table.loc[1.0, "firm_added_mw"])
        / table.loc[1.0, "fleet_battery_mw"]
    )
    # Re-valuing at firm capacity already found skips the search and gives the same rows.
    rows.to_csv(tmp_path / "years.csv", index=False)
    known = firm_from(tmp_path / "years.csv", 2035)
    assert known == {("Holistic Transition", s): f for s, f in zip(*_firm(rows), strict=True)}
    again = saturation_study(ROOT / "data/system", **study, known_firm=known)  # type: ignore[arg-type]
    pd.testing.assert_frame_equal(again, rows)


def _firm(rows: pd.DataFrame) -> tuple[list[float], list[float]]:
    return rows["battery_scale"].tolist(), rows["firm_added_mw"].tolist()


def test_cli_checks_pathways() -> None:
    result = CliRunner().invoke(app, ["system", "saturation", "--pathway", "Net Zero"])
    assert result.exit_code == 1 and "unknown pathway" in result.output
