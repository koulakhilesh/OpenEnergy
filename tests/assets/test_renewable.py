import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError, DataError
from openenergy.assets import RenewableSpec
from openenergy.data import ProfileSeries


def profile(values: list[float], technology: str = "solar", freq: str = "h") -> ProfileSeries:
    index = pd.date_range("2019-01-01", periods=len(values), freq=freq, tz="UTC")
    return ProfileSeries(pd.Series(values, index=index, dtype=float), technology, "GB")


def test_generation_scales_capacity_factor() -> None:
    plant = RenewableSpec(technology="solar", capacity_mw=10)
    generation = plant.generation_mw(profile([0.0, 0.5, 1.0]))
    assert generation.tolist() == pytest.approx([0.0, 5.0, 10.0])
    assert generation.name == "generation_mw"


def test_missing_capacity_factors_stay_missing() -> None:
    plant = RenewableSpec(technology="wind", capacity_mw=2)
    generation = plant.generation_mw(profile([0.5, np.nan], technology="wind"))
    assert np.isnan(generation.iloc[1])


def test_degradation_compounds_with_age() -> None:
    plant = RenewableSpec(technology="solar", capacity_mw=10, degradation_per_year=0.1)
    generation = plant.generation_mw(profile([1.0] * (2 * 8760 + 1)))
    assert generation.iloc[[0, 8760, 17520]].tolist() == pytest.approx([10.0, 9.0, 8.1])


def test_start_age_offsets_degradation() -> None:
    plant = RenewableSpec(technology="solar", capacity_mw=10, degradation_per_year=0.1)
    generation = plant.generation_mw(profile([1.0, 1.0]), start_age_years=2.0)
    assert generation.iloc[0] == pytest.approx(8.1)


def test_technology_must_match_profile() -> None:
    plant = RenewableSpec(technology="wind", capacity_mw=10)
    with pytest.raises(DataError, match="solar"):
        plant.generation_mw(profile([0.5, 0.5]))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"technology": "solar", "capacity_mw": 0.0}, "capacity_mw"),
        ({"technology": "solar", "capacity_mw": float("inf")}, "capacity_mw"),
        ({"technology": "", "capacity_mw": 1.0}, "technology"),
        ({"technology": "solar", "capacity_mw": 1.0, "degradation_per_year": 1.0}, "degradation"),
        ({"technology": "solar", "capacity_mw": 1.0, "degradation_per_year": -0.1}, "degradation"),
    ],
)
def test_spec_validation(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        RenewableSpec(**kwargs)  # type: ignore[arg-type]


def test_negative_start_age_rejected() -> None:
    plant = RenewableSpec(technology="solar", capacity_mw=1)
    with pytest.raises(ConfigError, match="start_age_years"):
        plant.generation_mw(profile([0.5, 0.5]), start_age_years=-1)
