import json
from datetime import date
from pathlib import Path

import pytest

from openenergy import ConfigError
from openenergy.assets import BatterySpec
from openenergy.dispatch import DispatchConfig
from openenergy.scenario import Scenario, load_scenario, run_scenario, write_outputs


def write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def test_load_resolves_data_path_relative_to_file(scenario_file: Path, opsd_csv: Path) -> None:
    scenario = load_scenario(scenario_file)
    assert scenario.name == "gb-test"
    assert scenario.data.path == opsd_csv.resolve()
    assert scenario.battery == BatterySpec(power_mw=1.0, energy_mwh=2.0)
    assert scenario.dispatch == DispatchConfig(degradation_cost=2.0)
    assert scenario.forecast.method == "naive_last_week"


def test_forecast_mapping_form(tmp_path: Path, opsd_csv: Path) -> None:
    path = write(
        tmp_path / "s.yaml",
        f"""
name: noisy
data: {{path: {opsd_csv}, start: 2019-01-02, end: 2019-01-20}}
battery: {{power_mw: 1, energy_mwh: 1}}
forecast: {{method: noisy_foresight, error_std: 5, seed: 3}}
""",
    )
    scenario = load_scenario(path)
    assert scenario.forecast.error_std == 5.0
    assert scenario.data.start == date(2019, 1, 2)


VALID = "name: x\ndata: {path: a.csv}\nbattery: {power_mw: 1, energy_mwh: 1}\n"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            "name: x\ndata: {path: a.csv}\nbattery: {power_mw: 1, energy_mwh: 1, colour: red}",
            "colour",
        ),
        ("name: x\ndata: {path: a.csv}\nbattery: {power_mw: -1, energy_mwh: 1}", "power_mw"),
        ("name: x\ndata: {path: a.csv}\nbattery: {power_mw: 1}", "energy_mwh"),
        (VALID.replace("name: x", "name: ../evil"), "name"),
        (VALID + "forecast: noisy_foresight", "error_std"),
        (VALID + "forecast: oracle", "forecast"),
        (VALID + "lead_hours: -1", "lead_hours"),
        ("- just\n- a list", "mapping"),
        ("name: [unclosed", "YAML"),
    ],
)
def test_invalid_scenarios_raise_config_error(tmp_path: Path, body: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_scenario(write(tmp_path / "bad.yaml", body))


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_scenario(tmp_path / "nope.yaml")


def test_run_scenario_with_benchmark(scenario_file: Path) -> None:
    run = run_scenario(load_scenario(scenario_file))
    assert run.result.forecaster == "naive_last_week"
    assert run.benchmark is not None
    assert list(run.benchmark.daily.index) == list(run.result.daily.index)
    assert run.summary.capture_ratio is not None
    assert 0 < run.summary.capture_ratio <= 1 + 1e-9
    assert run.summary.days == 14


def test_perfect_foresight_is_its_own_benchmark(tmp_path: Path, opsd_csv: Path) -> None:
    path = write(
        tmp_path / "pf.yaml",
        f"name: pf\ndata: {{path: {opsd_csv}}}\nbattery: {{power_mw: 1, energy_mwh: 2}}\n"
        "forecast: perfect_foresight\n",
    )
    run = run_scenario(load_scenario(path))
    assert run.benchmark is None
    assert run.summary.capture_ratio == pytest.approx(1.0)


def test_write_outputs(scenario_file: Path, tmp_path: Path) -> None:
    run = run_scenario(load_scenario(scenario_file))
    out = write_outputs(run, tmp_path / "out")
    assert sorted(p.name for p in out.iterdir()) == ["daily.csv", "intervals.csv", "summary.json"]
    payload = json.loads((out / "summary.json").read_text())
    assert payload["scenario"] == "gb-test"
    assert payload["summary"]["days"] == 14
    assert "2019-01-01" in payload["skipped"]
    assert "Open Power System Data" in payload["attribution"]
    assert (out / "intervals.csv").read_text().startswith("timestamp,price,forecast")


def test_lookahead_applies_to_forecast_and_benchmark(tmp_path: Path, opsd_csv: Path) -> None:
    path = write(
        tmp_path / "ahead.yaml",
        f"name: ahead\ndata: {{path: {opsd_csv}, start: 2019-01-08, end: 2019-01-21}}\n"
        "battery: {power_mw: 1, energy_mwh: 2}\ndispatch: {lookahead_days: 1}\n",
    )
    scenario = load_scenario(path)
    assert scenario.dispatch.lookahead_days == 1
    run = run_scenario(scenario)
    assert run.summary.days == 14
    assert run.summary.capture_ratio is not None and run.summary.capture_ratio > 0
    payload = json.loads((write_outputs(run, tmp_path / "out") / "summary.json").read_text())
    assert payload["config"]["dispatch"]["lookahead_days"] == 1
    bad = write(tmp_path / "bad.yaml", VALID + "dispatch: {lookahead_days: 9}\n")
    with pytest.raises(ConfigError, match="lookahead_days"):
        load_scenario(bad)


def test_scenario_is_immutable(scenario_file: Path) -> None:
    scenario = load_scenario(scenario_file)
    assert isinstance(scenario, Scenario)
    with pytest.raises(ValueError, match="frozen"):
        scenario.name = "other"  # type: ignore[misc]
