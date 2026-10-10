import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from openenergy import ConfigError
from openenergy.cli import app
from openenergy.data import GenerationMixSource, OPSDCsvSource, SystemInputs
from openenergy.system import build_system, solve
from openenergy.system.commitment import Commitment
from openenergy.system.scenario import (
    load_system_scenario,
    run_system_scenario,
    write_system_outputs,
)
from openenergy.system.validate import backcast, write_backcast

ROOT = Path(__file__).parents[2]
DATA = ROOT / "data/system"
OPSD = ROOT / "data/time_series/time_series_60min_singleindex_filtered.csv"
runner = CliRunner()


def window(start: date, end: date) -> tuple[pd.DataFrame, object]:
    mix = GenerationMixSource(DATA / "generation_mix.csv").mix(
        start, end, step=pd.Timedelta(hours=1)
    )
    return mix, OPSDCsvSource(OPSD).prices("GB_GBN", start, end)


def test_commitment_on_bundled_week_widens_daily_spread() -> None:
    mix, _ = window(date(2019, 1, 14), date(2019, 1, 20))
    inputs = SystemInputs(DATA)
    spec = build_system(mix, inputs)
    merit = solve(spec)
    uc = solve(spec, commitment=Commitment.from_inputs(inputs))
    assert uc.start_price is not None and uc.starts is not None
    spread = {
        name: (p.groupby(p.index.date).max() - p.groupby(p.index.date).min()).mean()
        for name, p in (("merit", merit.price), ("uc", uc.price), ("start", uc.start_price))
    }
    assert spread["uc"] > spread["merit"]
    assert spread["start"] > spread["merit"]
    assert uc.starts.to_numpy().sum() > 0
    assert uc.unserved.sum() == 0


def test_backcast_with_start_price(tmp_path: Path) -> None:
    mix, prices = window(date(2019, 6, 3), date(2019, 6, 5))
    inputs = SystemInputs(DATA)
    commitment = Commitment.from_inputs(inputs)
    result = backcast(mix, inputs, prices, commitment=commitment, price="start")
    year = result.years[0]
    assert year.daily_spread_model > 0
    assert year.daily_spread_actual > 0
    assert year.std_actual > 0
    out = write_backcast(result, tmp_path / "bc", commitment=commitment, price="start")
    summary = json.loads((out / "summary.json").read_text())
    assert summary["price"] == "start"
    assert summary["commitment"]["units"]["ccgt"]["unit_mw"] == 500.0
    assert any("Danish Energy Agency" in a for a in summary["attribution"])
    assert "Unit commitment" in summary["note"]
    with pytest.raises(ConfigError, match="needs unit commitment"):
        backcast(mix, inputs, prices, price="start")
    with pytest.raises(ConfigError, match="needs unit commitment"):
        solve(build_system(mix, inputs)).price_of("start")


def scenario(tmp_path: Path, **system: object) -> Path:
    raw = {
        "name": "uc-test",
        "system": {
            "data": str(DATA),
            "year": 2019,
            "start": "2019-06-03",
            "end": "2019-06-12",
            **system,
        },
        "battery": {"power_mw": 1.0, "energy_mwh": 2.0},
    }
    path = tmp_path / "uc.yaml"
    path.write_text(yaml.safe_dump(raw))
    return path


def test_scenario_with_commitment_values_battery_on_start_price(tmp_path: Path) -> None:
    run = run_system_scenario(
        load_system_scenario(scenario(tmp_path, commitment=True, price="start", lookahead_hours=12))
    )
    assert run.summary.price == "start"
    assert run.summary.backend == "commitment"
    assert run.summary.periods == 10 * 24
    assert run.summary.daily_spread > 0
    assert run.battery is not None
    out = write_system_outputs(run, tmp_path / "out")
    summary = json.loads((out / "summary.json").read_text())
    assert any("NREL" in a for a in summary["attribution"])
    assert "start_price" in (out / "dispatch.csv").read_text().splitlines()[0]


def test_scenario_validation(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="needs commitment"):
        load_system_scenario(scenario(tmp_path, price="start"))
    with pytest.raises(ConfigError, match="own solver"):
        load_system_scenario(scenario(tmp_path, commitment=True, backend="merit"))
    with pytest.raises(ConfigError, match="no days"):
        load_system_scenario(scenario(tmp_path, start="2019-07-01", end="2019-06-01"))


def test_cli_validate_with_commitment(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "system", "validate", "--data", str(DATA), "--prices", str(OPSD),
            "--start", "2019-06-03", "--end", "2019-06-04", "--commitment", "--price", "start",
            "--out", str(tmp_path / "bc"),
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "unit commitment, start price" in result.output
    assert "spread" in result.output
    bad = runner.invoke(app, ["system", "validate", "--price", "average"])
    assert bad.exit_code == 1
    assert "marginal or start" in bad.output
