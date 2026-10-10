from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from openenergy import DataError
from openenergy.data import (
    EMISSION_FACTORS,
    FLEET_ATTRIBUTION,
    MIX_ATTRIBUTION,
    GenerationMixSource,
    SystemInputs,
)
from openenergy.data.neso import FUELS

ROOT = Path(__file__).parents[2]
BUNDLED = ROOT / "data/system"


def write_mix(path: Path, periods: int = 4, **overrides: list[float]) -> Path:
    index = pd.date_range("2019-01-01", periods=periods, freq="30min", tz="UTC")
    frame = pd.DataFrame({fuel: [100.0] * periods for fuel in FUELS})
    for fuel, values in overrides.items():
        frame[fuel] = values
    frame["generation"] = frame[list(FUELS)].sum(axis=1)
    frame.insert(0, "utc_timestamp", index.strftime("%Y-%m-%dT%H:%M:%SZ"))
    frame.to_csv(path, index=False)
    return path


def test_mix_loads_and_averages(tmp_path: Path) -> None:
    source = GenerationMixSource(write_mix(tmp_path / "mix.csv", gas=[100, 200, 300, 400]))
    mix = source.mix()
    assert mix.index.tz is not None and str(mix.index.tz) == "UTC"
    assert mix["gas"].tolist() == [100, 200, 300, 400]
    hourly = source.mix(step=pd.Timedelta(hours=1))
    assert hourly["gas"].tolist() == [150, 350]
    assert hourly["generation"].iloc[0] == 150 + 100 * (len(FUELS) - 1)


def test_mix_hour_with_missing_half_is_missing(tmp_path: Path) -> None:
    path = write_mix(tmp_path / "mix.csv")
    frame = pd.read_csv(path)
    frame.loc[1, ["gas", "generation"]] = np.nan
    frame.to_csv(path, index=False)
    hourly = GenerationMixSource(path).mix(step=pd.Timedelta(hours=1))
    assert np.isnan(hourly["gas"].iloc[0])
    assert hourly["gas"].iloc[1] == 100


def test_mix_rejects_bad_files(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="not found"):
        GenerationMixSource(tmp_path / "missing.csv").mix()
    path = write_mix(tmp_path / "mix.csv")
    frame = pd.read_csv(path)
    frame.drop(columns="coal").to_csv(tmp_path / "short.csv", index=False)
    with pytest.raises(DataError, match="missing columns: coal"):
        GenerationMixSource(tmp_path / "short.csv").mix()
    frame.assign(generation=frame["generation"] + 50).to_csv(tmp_path / "sum.csv", index=False)
    with pytest.raises(DataError, match="add up"):
        GenerationMixSource(tmp_path / "sum.csv").mix()
    frame.assign(gas=-1.0, generation=frame["generation"] - 101).to_csv(
        tmp_path / "neg.csv", index=False
    )
    with pytest.raises(DataError, match="negative"):
        GenerationMixSource(tmp_path / "neg.csv").mix()
    with pytest.raises(DataError, match="multiple"):
        GenerationMixSource(path).mix(step=pd.Timedelta(minutes=45))


def test_mix_filters_whole_days(tmp_path: Path) -> None:
    path = write_mix(tmp_path / "mix.csv", periods=96)
    mix = GenerationMixSource(path).mix(start=date(2019, 1, 2), end=date(2019, 1, 2))
    assert len(mix) == 48
    assert mix.index[0] == pd.Timestamp("2019-01-02", tz="UTC")


def test_bundled_mix_covers_period() -> None:
    mix = GenerationMixSource(BUNDLED / "generation_mix.csv").mix(step=pd.Timedelta(hours=1))
    assert mix.index[0] == pd.Timestamp("2015-01-01", tz="UTC")
    assert mix.index[-1] == pd.Timestamp("2020-09-30 23:00", tz="UTC")
    assert not mix.isna().any().any()
    june = mix.loc["2019-06"]
    assert june["solar"].groupby(june.index.hour).mean().idxmax() in (11, 12)


def write_inputs(directory: Path) -> Path:
    pd.DataFrame(
        {
            "year": [2018, 2019],
            "ccgt_mw": [1000.0, 2000.0],
            "coal_mw": [500.0, 300.0],
            "gas_turbine_mw": [10.0, 10.0],
            "oil_engine_mw": [5.0, 5.0],
            "nuclear_mw": [100.0, 100.0],
            "pumped_storage_mw": [50.0, 50.0],
            "ccgt_efficiency": [0.48, 0.49],
            "coal_efficiency": [0.35, 0.33],
        }
    ).to_csv(directory / "fleet.csv", index=False)
    pd.DataFrame(
        {
            "year": [2019] * 4,
            "quarter": [1, 2, 3, 4],
            "coal_p_per_kwh": [0.9, 0.7, 0.8, 0.8],
            "oil_p_per_kwh": [4.0, 4.0, 4.0, 4.0],
            "gas_p_per_kwh": [1.7, 1.2, 1.25, 1.44],
        }
    ).to_csv(directory / "fuel_prices.csv", index=False)
    pd.DataFrame(
        {
            "valid_from": ["2018-04-01", "2019-04-01"],
            "eu_ets_usd_per_t": [12.0, 24.0],
            "fx_date": ["2018-03-29", "2019-04-01"],
            "usd_per_eur": [1.2, 1.2],
            "gbp_per_eur": [0.9, 0.9],
            "cps_gas_gbp_per_kwh": [0.00331, 0.00331],
            "cps_coal_gbp_per_gj": [1.5479, 1.5479],
        }
    ).to_csv(directory / "carbon_prices.csv", index=False)
    return directory


def test_capacity_interpolates_between_year_ends(tmp_path: Path) -> None:
    inputs = SystemInputs(write_inputs(tmp_path))
    index = pd.DatetimeIndex(["2019-01-01", "2019-07-02 12:00", "2020-01-01"], tz="UTC").as_unit(
        "s"
    )
    capacity = inputs.capacity(index)
    assert capacity["ccgt_mw"].iloc[0] == pytest.approx(1000.0)
    assert capacity["ccgt_mw"].iloc[1] == pytest.approx(1500.0, rel=1e-3)
    assert capacity["coal_mw"].iloc[2] == pytest.approx(300.0)
    with pytest.raises(DataError, match="covers"):
        inputs.capacity(pd.DatetimeIndex(["2018-06-01"], tz="UTC"))
    with pytest.raises(DataError, match="UTC"):
        inputs.capacity(pd.DatetimeIndex(["2019-06-01"]))


def test_efficiency_and_fuel_prices(tmp_path: Path) -> None:
    inputs = SystemInputs(write_inputs(tmp_path))
    assert inputs.efficiency(2019) == {"ccgt": 0.49, "coal": 0.33}
    with pytest.raises(DataError, match="2030"):
        inputs.efficiency(2030)
    index = pd.DatetimeIndex(["2019-03-31 23:00", "2019-04-01"], tz="UTC")
    prices = inputs.fuel_prices(index)
    assert prices["gas"].tolist() == pytest.approx([17.0, 12.0])
    assert prices["coal"].tolist() == pytest.approx([9.0, 7.0])
    with pytest.raises(DataError, match="2020 Q1"):
        inputs.fuel_prices(pd.DatetimeIndex(["2020-01-01"], tz="UTC"))


def test_carbon_prices_change_on_1_april(tmp_path: Path) -> None:
    inputs = SystemInputs(write_inputs(tmp_path))
    index = pd.DatetimeIndex(["2019-03-31 23:00", "2019-04-01"], tz="UTC")
    carbon = inputs.carbon_prices(index)
    assert carbon["eu_ets_gbp_per_t"].tolist() == pytest.approx([9.0, 18.0])
    assert carbon["cps_gas"].iloc[0] == pytest.approx(3.31)
    assert carbon["cps_coal"].iloc[0] == pytest.approx(1.5479 * 3.6)
    with pytest.raises(DataError, match="covers"):
        inputs.carbon_prices(pd.DatetimeIndex(["2018-01-01"], tz="UTC"))


def test_missing_input_file(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="not found"):
        SystemInputs(tmp_path).efficiency(2019)
    pd.DataFrame({"year": [2019]}).to_csv(tmp_path / "fleet.csv", index=False)
    with pytest.raises(DataError, match="missing columns"):
        SystemInputs(tmp_path).efficiency(2019)


def test_emission_factors_follow_cps_rates() -> None:
    assert EMISSION_FACTORS["gas"] == pytest.approx(0.1839, abs=1e-4)
    assert EMISSION_FACTORS["coal"] == pytest.approx(0.3096, abs=1e-4)


def test_bundled_inputs_cover_backcast() -> None:
    inputs = SystemInputs(BUNDLED)
    index = pd.date_range("2015-04-01", "2020-09-30 23:00", freq="1h", tz="UTC")
    assert not inputs.capacity(index).isna().any().any()
    assert not inputs.fuel_prices(index).isna().any().any()
    carbon = inputs.carbon_prices(index)
    assert carbon.loc["2019-06-01", "eu_ets_gbp_per_t"].iloc[0] == pytest.approx(18.68, abs=0.01)


def test_attributions_name_sources_and_licences() -> None:
    assert "Supported by National Energy SO Open Data" in MIX_ATTRIBUTION
    assert "not affiliated" in MIX_ATTRIBUTION
    for text in ("Open Government Licence", "World Bank", "CC BY 4.0", "European Central Bank"):
        assert text in FLEET_ATTRIBUTION
