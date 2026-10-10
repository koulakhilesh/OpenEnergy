"""Data after 2020: Ember prices in battery and system scenarios, backcast past 2020."""

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from openenergy import ConfigError
from openenergy.cli import app
from openenergy.data import EMBER_ATTRIBUTION, OPSD_ATTRIBUTION
from openenergy.scenario import load_scenario, run_scenario, write_outputs
from openenergy.system.scenario import (
    load_system_scenario,
    run_system_scenario,
    write_system_outputs,
)

ROOT = Path(__file__).parents[1]
EMBER = ROOT / "data/prices/gb_day_ahead_ember.csv"
OPSD = ROOT / "data/time_series/time_series_60min_singleindex_filtered.csv"
runner = CliRunner()
pytestmark = pytest.mark.skipif(not EMBER.exists(), reason="bundled Ember prices not present")


def battery_scenario(tmp_path: Path, **data: object) -> Path:
    raw = {
        "name": "ember-test",
        "data": {"source": "ember", "path": str(EMBER), "start": "2022-03-01",
                 "end": "2022-03-14", **data},
        "battery": {"power_mw": 1, "energy_mwh": 2},
    }  # fmt: skip
    path = tmp_path / "scenario.yaml"
    path.write_text(yaml.safe_dump(raw))
    return path


def test_battery_scenario_on_ember_prices(tmp_path: Path) -> None:
    run = run_scenario(load_scenario(battery_scenario(tmp_path)))
    assert run.summary.days == 14
    assert run.summary.currency == "GBP"
    assert run.attribution == EMBER_ATTRIBUTION
    summary = json.loads((write_outputs(run, tmp_path / "out") / "summary.json").read_text())
    assert "Ember" in summary["attribution"] and "CC BY 4.0" in summary["attribution"]


def test_assets_need_opsd_profiles(tmp_path: Path) -> None:
    raw = yaml.safe_load(battery_scenario(tmp_path).read_text())
    raw["assets"] = {"pv": {"capacity_mw": 1}}
    path = tmp_path / "assets.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ConfigError, match="OPSD capacity-factor profiles"):
        load_scenario(path)


def test_system_scenario_after_2020_cites_the_prices_it_used(tmp_path: Path) -> None:
    raw = {
        "name": "sys-2022",
        "system": {
            "data": str(ROOT / "data/system"),
            "prices": [str(OPSD), str(EMBER)],
            "year": 2022,
            "start": "2022-08-01",
            "end": "2022-08-07",
            "eu_ets_gbp_per_t": 70,
        },
    }
    path = tmp_path / "system.yaml"
    path.write_text(yaml.safe_dump(raw))
    scenario = load_system_scenario(path)
    assert scenario.system.ets_gbp_per_t == 70
    run = run_system_scenario(scenario)
    assert run.summary.actual_price_mean is not None and run.summary.actual_price_mean > 200
    summary = json.loads((write_system_outputs(run, tmp_path / "out") / "summary.json").read_text())
    assert EMBER_ATTRIBUTION in summary["attribution"]
    assert OPSD_ATTRIBUTION not in summary["attribution"]
    assert summary["config"]["system"]["ets_gbp_per_t"] == 70


def test_single_price_file_still_accepted(tmp_path: Path) -> None:
    path = tmp_path / "system.yaml"
    path.write_text(
        yaml.safe_dump(
            {"name": "one", "system": {"data": str(ROOT / "data/system"), "prices": str(OPSD),
                                      "year": 2019}}
        )
    )  # fmt: skip
    assert load_system_scenario(path).system.prices == [OPSD.resolve()]


def test_cli_validate_after_2020_uses_both_bundled_price_files(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["system", "validate", "--start", "2020-09-28", "--end", "2020-10-04",
         "--out", str(tmp_path / "bc")],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    summary = json.loads((tmp_path / "bc" / "summary.json").read_text())
    assert OPSD_ATTRIBUTION in summary["attribution"]
    assert EMBER_ATTRIBUTION in summary["attribution"]
    # OPSD has no price for 2020-09-30 23:00 and Ember does not fill gaps inside OPSD's span.
    assert summary["years"][0]["hours"] == 7 * 24 - 1
