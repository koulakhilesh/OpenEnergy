import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from openenergy import ConfigError
from openenergy.cli import app
from openenergy.system.scenario import (
    is_system_scenario,
    load_system_scenario,
    run_system_scenario,
    system_sweep,
    write_system_outputs,
)

ROOT = Path(__file__).parents[2]
runner = CliRunner()


def write(tmp_path: Path, **extra: object) -> Path:
    raw: dict[str, object] = {
        "name": "sys-test",
        "system": {
            "data": str(ROOT / "data/system"),
            "prices": str(ROOT / "data/time_series/time_series_60min_singleindex_filtered.csv"),
            "year": 2020,
        },
    }
    for key, value in extra.items():
        if key == "system":
            raw["system"].update(value)  # type: ignore[union-attr, arg-type]
        else:
            raw[key] = value
    path = tmp_path / "system.yaml"
    path.write_text(yaml.safe_dump(raw))
    return path


def test_runs_the_year_within_the_data_window(tmp_path: Path) -> None:
    run = run_system_scenario(load_system_scenario(write(tmp_path, system={"end": "2020-09-30"})))
    s = run.summary
    assert s.year == 2020
    assert s.periods == 274 * 24  # 2020-01-01 to 2020-09-30
    assert s.backend == "merit"
    assert s.actual_price_mean is not None and 20 < s.actual_price_mean < 50
    assert s.generation_twh["nuclear"] > 0
    assert s.unserved_mwh == 0
    assert run.battery is None


def test_adjustments_and_storage_flow_through(tmp_path: Path) -> None:
    pytest.importorskip("pypsa")
    path = write(
        tmp_path,
        system={
            "scale": {"wind": 3.0},
            "capacity_mw": {"coal": 0},
            "eu_ets_gbp_per_t": 50,
            "storage": {
                "fleet": {"power_mw": 2000, "hours": 4},
                "none": {"power_mw": 0, "hours": 1},
            },
        },
        battery={"power_mw": 1.0, "energy_mwh": 2.0},
    )
    run = run_system_scenario(load_system_scenario(path))
    assert run.summary.backend == "pypsa"
    assert run.summary.generation_twh["coal"] == 0
    assert run.summary.curtailment_twh > 0
    assert set(run.summary.storage_cycles) == {"fleet"}
    assert run.battery is not None and run.battery_benchmark is not None
    pf = run.battery_benchmark.revenue_per_mw_year
    assert pf is not None and run.battery.revenue_per_mw_year is not None
    assert pf >= run.battery.revenue_per_mw_year
    out = write_system_outputs(run, tmp_path / "out")
    summary = json.loads((out / "summary.json").read_text())
    assert summary["system"]["year"] == 2020
    assert "battery_perfect_foresight" in summary
    assert len(summary["attribution"]) == 3
    assert "perfect foresight" in summary["note"]
    dispatch = (out / "dispatch.csv").read_text().splitlines()[0]
    assert dispatch.startswith("utc_timestamp,price")
    assert "storage" in dispatch


def test_validation_errors_name_the_field(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"system\.year"):
        load_system_scenario(write(tmp_path, system={"year": 2012}))
    with pytest.raises(ConfigError, match="unknown keys tidal"):
        run_system_scenario(load_system_scenario(write(tmp_path, system={"scale": {"tidal": 2}})))
    with pytest.raises(ConfigError, match=r"storage\.fleet\.hours"):
        load_system_scenario(write(tmp_path, system={"storage": {"fleet": {"power_mw": 1}}}))


def test_detects_system_scenarios(tmp_path: Path) -> None:
    assert is_system_scenario(write(tmp_path))
    assert not is_system_scenario(ROOT / "examples/gb-2019-naive.yaml")


def test_system_sweep_keeps_grid_order(tmp_path: Path) -> None:
    table = system_sweep(write(tmp_path), {"system.scale.wind": [1, 2]})
    assert table["system.scale.wind"].tolist() == [1, 2]
    assert table["price_mean"].iloc[1] < table["price_mean"].iloc[0]
    with pytest.raises(ConfigError, match="exceed"):
        system_sweep(write(tmp_path), {"system.scale.wind": list(range(101))})


def test_cli_system_run_and_sweep(tmp_path: Path) -> None:
    path = write(tmp_path)
    result = runner.invoke(app, ["system", "run", str(path), "--out", str(tmp_path / "o")])
    assert result.exit_code == 0, result.output
    assert "sys-test (GB 2020, merit backend)" in result.output
    assert "actual" in result.output
    swept = runner.invoke(
        app,
        ["sweep", str(path), "--set", "system.scale.solar=1,2", "--out", str(tmp_path / "s.csv")],
    )
    assert swept.exit_code == 0, swept.output
    assert "price_mean" in swept.output
    assert (tmp_path / "s.csv").exists()


def test_cli_system_run_with_battery(tmp_path: Path) -> None:
    path = write(tmp_path, battery={"power_mw": 1.0, "energy_mwh": 2.0})
    result = runner.invoke(app, ["system", "run", str(path), "--out", str(tmp_path / "o")])
    assert result.exit_code == 0, result.output
    assert "battery on model" in result.output
    assert "perfect foresight" in result.output
