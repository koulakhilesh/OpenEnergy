import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from openenergy import DataError
from openenergy.cli import app
from openenergy.data import GenerationMixSource, OPSDCsvSource, PriceSeries, SystemInputs
from openenergy.system.validate import backcast, write_backcast

ROOT = Path(__file__).parents[2]
BUNDLED = ROOT / "data/system"
OPSD = ROOT / "data/time_series/time_series_60min_singleindex_filtered.csv"
runner = CliRunner()


def week(start: date, end: date) -> tuple[pd.DataFrame, PriceSeries]:
    mix = GenerationMixSource(BUNDLED / "generation_mix.csv").mix(
        start, end, step=pd.Timedelta(hours=1)
    )
    return mix, OPSDCsvSource(OPSD).prices("GB_GBN", start, end)


def test_backcast_compares_with_history() -> None:
    mix, prices = week(date(2019, 12, 25), date(2020, 1, 7))
    result = backcast(mix, SystemInputs(BUNDLED), prices)
    assert [y.year for y in result.years] == [2019, 2020]
    first = result.years[0]
    assert first.hours == 7 * 24 - prices.prices.loc["2019"].isna().sum()
    hourly = result.hourly.loc["2019"]
    assert first.price_model == pytest.approx(
        hourly["price_model"][hourly["price_actual"].notna()].mean()
    )
    assert first.gas_twh_actual == pytest.approx(mix.loc["2019", "gas"].sum() / 1e6)
    assert first.gas_twh_model + first.coal_twh_model == pytest.approx(
        first.gas_twh_actual + first.coal_twh_actual, rel=1e-3
    )
    assert -1 <= first.correlation <= 1
    assert first.unserved_mwh == 0
    assert set(result.results) == {2019, 2020}


def test_backcast_requires_matching_steps() -> None:
    mix, prices = week(date(2019, 6, 1), date(2019, 6, 2))
    half_hourly = GenerationMixSource(BUNDLED / "generation_mix.csv").mix(
        date(2019, 6, 1), date(2019, 6, 2)
    )
    with pytest.raises(DataError, match="differs"):
        backcast(half_hourly, SystemInputs(BUNDLED), prices)
    with pytest.raises(DataError, match="two periods"):
        backcast(mix.iloc[:1], SystemInputs(BUNDLED), prices)
    gap = PriceSeries(prices.prices * np.nan, currency="GBP", zone="GB_GBN")
    with pytest.raises(DataError, match="no actual prices"):
        backcast(mix, SystemInputs(BUNDLED), gap)


def test_write_backcast_cites_sources(tmp_path: Path) -> None:
    mix, prices = week(date(2019, 6, 1), date(2019, 6, 3))
    out = write_backcast(backcast(mix, SystemInputs(BUNDLED), prices), tmp_path / "bc")
    summary = json.loads((out / "summary.json").read_text())
    assert summary["years"][0]["year"] == 2019
    assert summary["assumptions"]["availability"] == 0.9
    assert any("Supported by National Energy SO Open Data" in a for a in summary["attribution"])
    assert "No parameter is fitted" in summary["note"]
    assert len(pd.read_csv(out / "hourly.csv")) == 72
    assert list(pd.read_csv(out / "backcast.csv")["year"]) == [2019]


def test_cli_system_validate(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "system", "validate", "--data", str(BUNDLED), "--prices", str(OPSD),
            "--start", "2019-06-01", "--end", "2019-06-07", "--out", str(tmp_path / "bc"),
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "2019" in result.output
    assert (tmp_path / "bc" / "summary.json").exists()


def test_cli_system_validate_rejects_bad_dates() -> None:
    result = runner.invoke(app, ["system", "validate", "--start", "June"])
    assert result.exit_code == 1
    assert "YYYY-MM-DD" in result.output
