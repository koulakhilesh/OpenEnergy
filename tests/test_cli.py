from pathlib import Path

import pytest
from typer.testing import CliRunner

import openenergy
from openenergy.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert openenergy.__version__ in result.output


def test_run_writes_outputs_and_prints_summary(scenario_file: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(app, ["run", str(scenario_file), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert "gb-test" in result.output
    assert "capture ratio" in result.output
    assert (out / "summary.json").exists()


def test_run_defaults_output_to_outputs_name(
    scenario_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["run", str(scenario_file)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "outputs" / "gb-test" / "daily.csv").exists()


def test_compare_ranks_scenarios(scenario_file: Path, tmp_path: Path) -> None:
    pf = scenario_file.with_name("pf.yaml")
    pf.write_text(
        scenario_file.read_text()
        .replace("gb-test", "gb-pf")
        .replace("naive_last_week", "perfect_foresight")
    )
    result = runner.invoke(app, ["compare", str(scenario_file), str(pf)])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0].split()[0] == "scenario"
    assert lines[1].split()[0] == "gb-pf"
    assert lines[2].split()[0] == "gb-test"


def test_data_info(opsd_csv: Path) -> None:
    result = runner.invoke(app, ["data", "info", str(opsd_csv)])
    assert result.exit_code == 0, result.output
    assert "GB_GBN" in result.output
    assert "GBP" in result.output
    assert "21/21 complete days" in result.output


def test_errors_are_reported_without_traceback(tmp_path: Path) -> None:
    result = runner.invoke(app, ["run", str(tmp_path / "missing.yaml")])
    assert result.exit_code == 1
    assert "error:" in result.output
    assert "Traceback" not in result.output
