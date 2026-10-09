from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from openenergy import ConfigError
from openenergy.cli import app
from openenergy.scenario import apply_overrides, parse_assignment, sweep


def test_parse_assignment_types_values() -> None:
    assert parse_assignment("battery.energy_mwh=1,2,4") == ("battery.energy_mwh", [1, 2, 4])
    assert parse_assignment("forecast=naive_last_week,perfect_foresight") == (
        "forecast",
        ["naive_last_week", "perfect_foresight"],
    )
    assert parse_assignment("dispatch.end_soc=0.5") == ("dispatch.end_soc", [0.5])


@pytest.mark.parametrize("text", ["battery.energy_mwh", "=1,2", "battery.energy_mwh=", "a..b=1"])
def test_parse_assignment_rejects_bad_input(text: str) -> None:
    with pytest.raises(ConfigError, match="key=value"):
        parse_assignment(text)


def test_apply_overrides_sets_nested_keys_without_mutating() -> None:
    raw = {"name": "x", "battery": {"power_mw": 1}}
    updated = apply_overrides(raw, {"battery.energy_mwh": 4, "dispatch.end_soc": 0.5})
    assert updated["battery"] == {"power_mw": 1, "energy_mwh": 4}
    assert updated["dispatch"] == {"end_soc": 0.5}
    assert raw == {"name": "x", "battery": {"power_mw": 1}}


def test_apply_overrides_rejects_setting_inside_a_value() -> None:
    with pytest.raises(ConfigError, match="forecast"):
        apply_overrides({"forecast": "naive_last_week"}, {"forecast.seed": 3})


def test_sweep_runs_every_combination(scenario_file: Path) -> None:
    table = sweep(
        scenario_file,
        {"battery.energy_mwh": [1, 4], "dispatch.degradation_cost": [0, 10]},
    )
    assert len(table) == 4
    assert list(table.columns[:2]) == ["battery.energy_mwh", "dispatch.degradation_cost"]
    assert {"total", "revenue_per_mw_year", "capture_ratio", "equivalent_cycles"} <= set(
        table.columns
    )
    assert table["total"].is_monotonic_decreasing
    bigger = table[table["battery.energy_mwh"] == 4]["total"].max()
    smaller = table[table["battery.energy_mwh"] == 1]["total"].max()
    assert bigger > smaller


def test_sweep_reports_invalid_key(scenario_file: Path) -> None:
    with pytest.raises(ConfigError, match=r"battery\.colour"):
        sweep(scenario_file, {"battery.colour": ["red"]})


def test_sweep_limits_combinations(scenario_file: Path) -> None:
    with pytest.raises(ConfigError, match="combinations"):
        sweep(
            scenario_file,
            {"battery.energy_mwh": list(range(1, 21)), "battery.power_mw": list(range(1, 21))},
        )


def test_cli_sweep_prints_and_writes_csv(scenario_file: Path, tmp_path: Path) -> None:
    out = tmp_path / "sweep.csv"
    result = CliRunner().invoke(
        app,
        ["sweep", str(scenario_file), "--set", "battery.energy_mwh=1,2", "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0].split()[0] == "battery.energy_mwh"
    assert len([line for line in lines if line.strip()]) >= 3
    assert len(pd.read_csv(out)) == 2


def test_cli_sweep_requires_set(scenario_file: Path) -> None:
    result = CliRunner().invoke(app, ["sweep", str(scenario_file)])
    assert result.exit_code == 1
    assert "--set" in result.output
