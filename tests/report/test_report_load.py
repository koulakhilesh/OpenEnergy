import json
from pathlib import Path

import pandas as pd
import pytest

from openenergy import DataError
from openenergy.report import (
    BackcastOutput,
    BatteryOutput,
    SweepOutput,
    SystemOutput,
    load_output,
)


def test_detects_every_kind(
    battery_dir: Path, system_dir: Path, backcast_dir: Path, sweep_csv: Path
) -> None:
    battery = load_output(battery_dir)
    assert isinstance(battery, BatteryOutput)
    assert battery.name == "gb-test"
    assert battery.benchmark_daily is not None
    assert battery.daily.index.equals(battery.benchmark_daily.index)
    assert str(battery.intervals.index.tz) == "UTC"
    system = load_output(system_dir)
    assert isinstance(system, SystemOutput) and len(system.dispatch) == 7 * 24
    back = load_output(backcast_dir)
    assert isinstance(back, BackcastOutput) and list(back.years["year"]) == [2019]
    sweep = load_output(sweep_csv)
    assert isinstance(sweep, SweepOutput) and sweep.keys == ["battery.energy_mwh"]


def test_rejects_what_it_cannot_read(tmp_path: Path, battery_dir: Path) -> None:
    with pytest.raises(DataError, match="no output directory"):
        load_output(tmp_path / "missing")
    (tmp_path / "empty").mkdir()
    with pytest.raises(DataError, match=r"no daily\.csv"):
        load_output(tmp_path / "empty")
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    with pytest.raises(DataError, match="not a sweep CSV"):
        load_output(bad)
    (battery_dir / "summary.json").write_text("{not json")
    with pytest.raises(DataError, match="not valid JSON"):
        load_output(battery_dir)
    (battery_dir / "summary.json").write_text(json.dumps([1, 2]))
    with pytest.raises(DataError, match="JSON object"):
        load_output(battery_dir)
    (battery_dir / "summary.json").unlink()
    with pytest.raises(DataError, match=r"no summary\.json"):
        load_output(battery_dir)


def test_missing_files_and_columns(battery_dir: Path) -> None:
    (battery_dir / "intervals.csv").unlink()
    with pytest.raises(DataError, match="missing"):
        load_output(battery_dir)
    pd.DataFrame({"x": [1]}).to_csv(battery_dir / "intervals.csv", index=False)
    with pytest.raises(DataError, match="'timestamp'"):
        load_output(battery_dir)
