"""Output directories of every kind, written by the real commands on small windows."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml

from openenergy.data import GenerationMixSource, SystemInputs, gb_prices
from openenergy.scenario import load_scenario, run_scenario, write_outputs
from openenergy.system.scenario import (
    load_system_scenario,
    run_system_scenario,
    write_system_outputs,
)
from openenergy.system.validate import backcast, write_backcast

ROOT = Path(__file__).parents[2]


@pytest.fixture
def battery_dir(scenario_file: Path, tmp_path: Path) -> Path:
    return write_outputs(run_scenario(load_scenario(scenario_file)), tmp_path / "battery")


@pytest.fixture
def system_dir(tmp_path: Path) -> Path:
    raw = {
        "name": "sys",
        "system": {"data": str(ROOT / "data/system"), "year": 2019, "start": "2019-03-01",
                   "end": "2019-03-07"},
    }  # fmt: skip
    path = tmp_path / "system.yaml"
    path.write_text(yaml.safe_dump(raw))
    run = run_system_scenario(load_system_scenario(path))
    return write_system_outputs(run, tmp_path / "system")


@pytest.fixture
def backcast_dir(tmp_path: Path) -> Path:
    first, last = date(2019, 3, 1), date(2019, 3, 7)
    mix = GenerationMixSource(ROOT / "data/system/generation_mix.csv").mix(
        first, last, step=pd.Timedelta(hours=1)
    )
    prices, sources = gb_prices(
        [ROOT / "data/time_series/time_series_60min_singleindex_filtered.csv"], first, last
    )
    result = backcast(mix, SystemInputs(ROOT / "data/system"), prices)
    return write_backcast(result, tmp_path / "backcast", price_attribution=sources)


@pytest.fixture
def sweep_csv(tmp_path: Path) -> Path:
    path = tmp_path / "sweep.csv"
    pd.DataFrame(
        {
            "battery.energy_mwh": [4, 2, 1],
            "total": [300.0, 250.0, 150.0],
            "revenue_per_mw_year": [3000.0, 2500.0, 1500.0],
            "capture_ratio": [0.8, 0.75, 0.7],
            "equivalent_cycles": [10.0, 12.0, 14.0],
            "final_soh": [1.0, 1.0, 1.0],
            "emissions_t": [None, None, None],
        }
    ).to_csv(path, index=False)
    return path
