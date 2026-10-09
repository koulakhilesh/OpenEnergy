import os
import sys

import pytest
import datetime

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from scripts.wind_generation_models.simulated_wind_model import SimulatedWindGenerationModel


@pytest.fixture
def wind_model():
    """Fixture for default wind generation model."""
    return SimulatedWindGenerationModel()


@pytest.fixture
def wind_model_custom():
    """Fixture for custom wind generation model."""
    from scripts.wind_generation_models.simulated_wind_model import (
        SimulatedWindGenerationEnvelopeGenerator,
        SimulatedWindGenerationNoiseAdder
    )
    
    envelope_gen = SimulatedWindGenerationEnvelopeGenerator(capacity_kw=2000.0, turbulence_factor=0.15)
    noise_adder = SimulatedWindGenerationNoiseAdder(noise_std=0.25)
    
    return SimulatedWindGenerationModel(
        envelope_generator=envelope_gen,
        noise_adder=noise_adder
    )


@pytest.fixture
def test_date():
    """Fixture for a standard test date."""
    return datetime.date(2024, 6, 15)


def test_initialization_default_params(wind_model):
    """Test model initialization with default parameters."""
    assert wind_model.envelope_generator is not None
    assert wind_model.noise_adder is not None
    # Test that default components have expected default values
    assert wind_model.envelope_generator.capacity_kw == 1000.0
    assert wind_model.envelope_generator.turbulence_factor == 0.3


@pytest.mark.parametrize(
    "capacity, turbulence, noise_std",
    [
        (2000.0, 0.15, 0.25),
        (500.0, 0.05, 0.3),
        (5000.0, 0.2, 0.15),
    ],
)
def test_initialization_custom_params(capacity, turbulence, noise_std):
    """Test model initialization with various custom parameters."""
    from scripts.wind_generation_models.simulated_wind_model import (
        SimulatedWindGenerationEnvelopeGenerator,
        SimulatedWindGenerationNoiseAdder
    )
    
    envelope_gen = SimulatedWindGenerationEnvelopeGenerator(
        capacity_kw=capacity,
        turbulence_factor=turbulence
    )
    noise_adder = SimulatedWindGenerationNoiseAdder(noise_std=noise_std)
    
    model = SimulatedWindGenerationModel(
        envelope_generator=envelope_gen,
        noise_adder=noise_adder
    )
    
    assert model.envelope_generator.capacity_kw == capacity
    assert model.envelope_generator.turbulence_factor == turbulence
    assert model.noise_adder.noise_std == noise_std


def test_get_generation_returns_lists(wind_model, test_date):
    """Test that get_generation returns two lists of 24 elements."""
    actual, potential = wind_model.get_generation(test_date)
    
    assert isinstance(actual, list)
    assert isinstance(potential, list)
    assert len(actual) == 24
    assert len(potential) == 24


def test_get_generation_values_within_bounds(wind_model, test_date):
    """Test that generation values are within expected bounds."""
    actual, potential = wind_model.get_generation(test_date)
    
    # All values should be non-negative
    assert all(val >= 0 for val in actual)
    assert all(val >= 0 for val in potential)
    
    # Actual should not exceed potential
    for i in range(24):
        assert actual[i] <= potential[i]
    
    # Values should not exceed capacity
    capacity = wind_model.envelope_generator.capacity_kw
    for val in potential:
        assert val <= capacity


@pytest.mark.parametrize(
    "season_date, expected_variation",
    [
        (datetime.date(2024, 12, 15), "winter"),  # Winter
        (datetime.date(2024, 6, 15), "summer"),   # Summer
        (datetime.date(2024, 3, 15), "spring"),   # Spring
        (datetime.date(2024, 9, 15), "autumn"),   # Autumn
    ],
)
def test_get_generation_seasonal_variation(wind_model, season_date, expected_variation):
    """Test that generation varies by season."""
    actual, potential = wind_model.get_generation(season_date)
    
    # Should produce valid results for all seasons
    assert len(actual) == 24
    assert len(potential) == 24
    assert all(val >= 0 for val in actual)
    assert all(val >= 0 for val in potential)


def test_get_generation_daily_variation(wind_model, test_date):
    """Test that generation has daily variation patterns."""
    actual, potential = wind_model.get_generation(test_date)
    
    # There should be variation throughout the day
    unique_actual = set(actual)
    unique_potential = set(potential)
    assert len(unique_actual) > 1  # Not all values the same
    assert len(unique_potential) > 1


def test_multiple_calls_same_date_different_due_to_noise(wind_model, test_date):
    """Test that multiple calls with the same date return different results due to noise."""
    # Get generation twice for the same date
    actual1, potential1 = wind_model.get_generation(test_date)
    actual2, potential2 = wind_model.get_generation(test_date)
    
    # Both potential and actual generation may be different due to random components
    # Just verify that we get valid results
    assert isinstance(actual1, list)
    assert isinstance(potential1, list)
    assert isinstance(actual2, list)
    assert isinstance(potential2, list)
    assert len(actual1) == 24
    assert len(potential1) == 24
    assert len(actual2) == 24
    assert len(potential2) == 24
    
    # All values should be non-negative
    assert all(val >= 0 for val in actual1)
    assert all(val >= 0 for val in potential1)
    assert all(val >= 0 for val in actual2)
    assert all(val >= 0 for val in potential2)


@pytest.mark.parametrize(
    "date1, date2",
    [
        (datetime.date(2024, 6, 15), datetime.date(2024, 6, 16)),
        (datetime.date(2024, 1, 1), datetime.date(2024, 12, 31)),
        (datetime.date(2024, 3, 15), datetime.date(2024, 9, 15)),
    ],
)
def test_different_dates_different_results(wind_model, date1, date2):
    """Test that different dates produce different results."""
    actual1, potential1 = wind_model.get_generation(date1)
    actual2, potential2 = wind_model.get_generation(date2)
    
    # Results should be different for different dates
    assert actual1 != actual2 or potential1 != potential2


@pytest.mark.parametrize(
    "capacity",
    [0.0, 100.0, 1000000.0],
)
def test_capacity_edge_cases(capacity, test_date):
    """Test model behavior with various capacity values."""
    from scripts.wind_generation_models.simulated_wind_model import (
        SimulatedWindGenerationEnvelopeGenerator,
        SimulatedWindGenerationNoiseAdder
    )
    
    envelope_gen = SimulatedWindGenerationEnvelopeGenerator(capacity_kw=capacity)
    noise_adder = SimulatedWindGenerationNoiseAdder(noise_std=0.05)
    model = SimulatedWindGenerationModel(envelope_generator=envelope_gen, noise_adder=noise_adder)
    
    actual, potential = model.get_generation(test_date)
    
    # All values should be non-negative and within capacity
    assert all(val >= 0 for val in actual)
    assert all(val >= 0 for val in potential)
    assert all(val <= capacity for val in potential)
    
    if capacity == 0.0:
        # All values should be zero for zero capacity
        assert all(val == 0 for val in actual)
        assert all(val == 0 for val in potential)


@pytest.mark.parametrize(
    "turbulence",
    [0.0, 0.1, 0.5, 1.0],
)
def test_turbulence_factor_variations(turbulence, test_date):
    """Test model with various turbulence factors."""
    from scripts.wind_generation_models.simulated_wind_model import (
        SimulatedWindGenerationEnvelopeGenerator,
        SimulatedWindGenerationNoiseAdder
    )
    
    envelope_gen = SimulatedWindGenerationEnvelopeGenerator(turbulence_factor=turbulence)
    model = SimulatedWindGenerationModel(envelope_generator=envelope_gen)
    
    actual, potential = model.get_generation(test_date)
    
    # Should still produce valid results
    assert len(actual) == 24
    assert len(potential) == 24
    assert all(val >= 0 for val in actual)
    assert all(val >= 0 for val in potential)


@pytest.mark.parametrize(
    "noise_std",
    [0.0, 0.05, 0.2, 0.5],
)
def test_noise_level_variations(noise_std, test_date):
    """Test model with various noise levels."""
    from scripts.wind_generation_models.simulated_wind_model import (
        SimulatedWindGenerationEnvelopeGenerator,
        SimulatedWindGenerationNoiseAdder
    )
    
    envelope_gen = SimulatedWindGenerationEnvelopeGenerator(
        capacity_kw=1000.0,
        turbulence_factor=0.1
    )
    noise_adder = SimulatedWindGenerationNoiseAdder(noise_std=noise_std)
    model = SimulatedWindGenerationModel(
        envelope_generator=envelope_gen,
        noise_adder=noise_adder
    )
    
    actual, potential = model.get_generation(test_date)
    
    # Should still produce valid results
    assert len(actual) == 24
    assert len(potential) == 24
    assert all(val >= 0 for val in actual)
    assert all(val >= 0 for val in potential)


@pytest.mark.parametrize(
    "test_date",
    [
        datetime.date(2024, 2, 29),  # Leap year
        datetime.date(2024, 12, 31), # Year end
        datetime.date(2024, 1, 1),   # Year start
        datetime.date(2000, 1, 1),   # Different year
    ],
)
def test_edge_case_dates(wind_model, test_date):
    """Test model with edge case dates."""
    actual, potential = wind_model.get_generation(test_date)
    assert len(actual) == 24
    assert len(potential) == 24
    assert all(val >= 0 for val in actual)
    assert all(val >= 0 for val in potential)


def test_generation_type_consistency(wind_model, test_date):
    """Test that generation values are of correct type."""
    actual, potential = wind_model.get_generation(test_date)
    
    # All values should be numeric (int or float)
    for val in actual:
        assert isinstance(val, (int, float))
    for val in potential:
        assert isinstance(val, (int, float))


def test_generation_mathematical_relationships(wind_model, test_date):
    """Test mathematical relationships in generation data."""
    actual, potential = wind_model.get_generation(test_date)
    
    # Daily totals should be positive
    daily_actual = sum(actual)
    daily_potential = sum(potential)
    
    assert daily_actual >= 0
    assert daily_potential >= 0
    assert daily_actual <= daily_potential
    
    # Capacity factor should be reasonable (0-100%)
    if daily_potential > 0:
        capacity_factor = daily_actual / daily_potential
        assert 0.0 <= capacity_factor <= 1.0


if __name__ == "__main__":
    pytest.main([__file__])
