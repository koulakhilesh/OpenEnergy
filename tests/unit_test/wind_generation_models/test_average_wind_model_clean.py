import os
import sys

import pytest
import datetime
from unittest.mock import Mock, patch
import pandas as pd

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from scripts.wind_generation_models.average_wind_model import HistoricalAverageWindGenerationModel
from scripts.wind_generation_models.wind_data_helper import WindDataHelper
from scripts.shared.interfaces import IDataProvider


@pytest.fixture
def mock_data_provider():
    """Fixture for mock data provider."""
    return Mock(spec=IDataProvider)


@pytest.fixture
def wind_model(mock_data_provider):
    """Fixture for default wind generation model."""
    return HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0,
        lookback_days=30
    )


@pytest.fixture
def test_date():
    """Fixture for a standard test date."""
    return datetime.date(2024, 6, 15)


def test_initialization_default_params(mock_data_provider):
    """Test model initialization with default parameters."""
    model = HistoricalAverageWindGenerationModel(data_provider=mock_data_provider)
    
    assert model.data_provider == mock_data_provider
    assert model.capacity_kw == 1000.0
    assert model.lookback_days == 30
    assert isinstance(model.wind_data_helper, WindDataHelper)


@pytest.mark.parametrize(
    "capacity,lookback_days",
    [
        (500.0, 14),
        (2000.0, 60),
        (1500.0, 7),
    ]
)
def test_initialization_custom_params(mock_data_provider, capacity, lookback_days):
    """Test model initialization with custom parameters."""
    mock_data_provider.get_data.return_value = pd.DataFrame({
        'wind_generation': [100.0, 150.0, 200.0],
        'utc_timestamp': pd.date_range('2024-01-01', periods=3, freq='h')
    })
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=capacity,
        lookback_days=lookback_days
    )
    
    assert model.capacity_kw == capacity
    assert model.lookback_days == lookback_days


def test_get_generation_with_data(mock_data_provider, test_date):
    """Test get_generation when historical data is available."""
    # Mock data provider to return historical data
    mock_data_provider.get_data.return_value = pd.DataFrame({
        'wind_generation': [100.0, 150.0, 200.0],
        'utc_timestamp': pd.date_range('2024-01-01', periods=3, freq='h')
    })
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0
    )
    
    actual_generation, potential_generation = model.get_generation(test_date)
    
    # Should return lists with 24 hours of data
    assert len(actual_generation) == 24
    assert len(potential_generation) == 24
    assert all(isinstance(gen, (int, float)) for gen in actual_generation)
    assert all(isinstance(gen, (int, float)) for gen in potential_generation)


def test_get_generation_no_data(mock_data_provider, test_date):
    """Test get_generation when no historical data is available."""
    # Mock data provider to return empty DataFrame
    mock_data_provider.get_data.return_value = pd.DataFrame()
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0
    )
    
    actual_generation, potential_generation = model.get_generation(test_date)
    
    # Should still return lists with 24 hours of data (default pattern)
    assert len(actual_generation) == 24
    assert len(potential_generation) == 24
    assert all(isinstance(gen, (int, float)) for gen in actual_generation)
    assert all(gen >= 0 for gen in actual_generation)


def test_get_generation_values_within_bounds(wind_model, test_date):
    """Test that all generated values are within expected bounds."""
    actual_generation, potential_generation = wind_model.get_generation(test_date)
    
    # Check bounds
    assert all(0 <= gen <= wind_model.capacity_kw for gen in actual_generation)
    assert all(gen == wind_model.capacity_kw for gen in potential_generation)


def test_get_generation_exception_handling(mock_data_provider, test_date):
    """Test get_generation exception handling."""
    # Mock data provider to return problematic data
    mock_data_provider.get_data.return_value = pd.DataFrame({
        'wind_generation': [100.0, 150.0, 200.0],
        'utc_timestamp': pd.date_range('2024-01-01', periods=3, freq='h')
    })
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0
    )
    
    # Mock wind_data_helper to raise an exception
    with patch.object(model.wind_data_helper, 'get_current_date', side_effect=Exception("Test error")):
        actual_generation, potential_generation = model.get_generation(test_date)
        
        # Should fallback to default pattern
        assert len(actual_generation) == 24
        assert len(potential_generation) == 24
        assert all(isinstance(gen, (int, float)) for gen in actual_generation)


@pytest.mark.parametrize(
    "capacity",
    [100.0, 500.0, 1000.0, 2000.0, 5000.0]
)
def test_capacity_variations(mock_data_provider, capacity, test_date):
    """Test wind generation with different capacity values."""
    mock_data_provider.get_data.return_value = pd.DataFrame({
        'wind_generation': [capacity * 0.8] * 24,  # High generation
        'utc_timestamp': pd.date_range('2024-01-01', periods=24, freq='h')
    })
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=capacity
    )
    
    actual_generation, potential_generation = model.get_generation(test_date)
    
    # Generation should never exceed capacity
    assert all(gen <= capacity for gen in actual_generation)
    assert all(gen == capacity for gen in potential_generation)


@pytest.mark.parametrize(
    "season_date,season_name",
    [
        (datetime.date(2024, 3, 21), "spring"),
        (datetime.date(2024, 6, 21), "summer"),
        (datetime.date(2024, 9, 21), "autumn"),
        (datetime.date(2024, 12, 21), "winter"),
    ]
)
def test_seasonal_variations(wind_model, season_date, season_name):
    """Test that the model handles different seasons appropriately."""
    actual_generation, potential_generation = wind_model.get_generation(season_date)
    
    # Basic validation for all seasons
    assert len(actual_generation) == 24
    assert len(potential_generation) == 24
    assert all(gen >= 0 for gen in actual_generation)


def test_multiple_calls_consistency(wind_model, test_date):
    """Test that multiple calls to get_generation return consistent results."""
    # Call multiple times
    results = []
    for _ in range(3):
        result = wind_model.get_generation(test_date)
        results.append(result)
    
    # All results should be identical
    for i in range(1, len(results)):
        assert results[i][0] == results[0][0]  # actual_generation
        assert results[i][1] == results[0][1]  # potential_generation


@pytest.mark.parametrize(
    "lookback_days",
    [7, 14, 30, 60, 90]
)
def test_lookback_days_variations(mock_data_provider, lookback_days, test_date):
    """Test wind generation with different lookback day configurations."""
    # Create mock data spanning the lookback period
    start_date = test_date - datetime.timedelta(days=lookback_days + 5)
    mock_data_provider.get_data.return_value = pd.DataFrame({
        'wind_generation': [150.0] * (lookback_days * 24),
        'utc_timestamp': pd.date_range(start_date, periods=lookback_days * 24, freq='h')
    })
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0,
        lookback_days=lookback_days
    )
    
    actual_generation, potential_generation = model.get_generation(test_date)
    
    assert len(actual_generation) == 24
    assert len(potential_generation) == 24
    assert model.lookback_days == lookback_days


@pytest.mark.parametrize(
    "test_date",
    [
        datetime.date(2024, 2, 29),  # Leap year
        datetime.date(2024, 1, 1),   # New Year
        datetime.date(2024, 12, 31), # New Year's Eve
    ]
)
def test_edge_case_dates(wind_model, test_date):
    """Test wind generation with edge case dates."""
    actual_generation, potential_generation = wind_model.get_generation(test_date)
    
    assert len(actual_generation) == 24
    assert len(potential_generation) == 24
    assert all(isinstance(gen, (int, float)) for gen in actual_generation)


def test_generation_type_consistency(wind_model, test_date):
    """Test that generation values are consistently typed."""
    actual_generation, potential_generation = wind_model.get_generation(test_date)
    
    # Check that all values are numeric
    assert all(isinstance(gen, (int, float)) for gen in actual_generation)
    assert all(isinstance(gen, (int, float)) for gen in potential_generation)
    
    # Check that no values are NaN or infinite
    assert all(not (isinstance(gen, float) and (gen != gen or gen == float('inf') or gen == float('-inf'))) 
              for gen in actual_generation)


def test_generation_mathematical_relationships(wind_model, test_date):
    """Test mathematical relationships between generation values."""
    actual_generation, potential_generation = wind_model.get_generation(test_date)
    
    # Actual generation should never exceed potential
    for actual, potential in zip(actual_generation, potential_generation):
        assert actual <= potential
    
    # All potential generation should be equal to capacity
    assert all(gen == wind_model.capacity_kw for gen in potential_generation)


def test_get_generation_with_empty_hour_data(mock_data_provider):
    """Test get_generation when some hours have no historical data."""
    # Create data with gaps (only some hours)
    mock_data_provider.get_data.return_value = pd.DataFrame({
        'wind_generation': [100.0, 150.0],  # Only 2 hours
        'utc_timestamp': [
            datetime.datetime(2024, 1, 1, 0, 0),
            datetime.datetime(2024, 1, 1, 12, 0)
        ]
    })
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0
    )
    
    test_date = datetime.date(2024, 6, 15)
    actual_generation, potential_generation = model.get_generation(test_date)
    
    # Should still return 24 hours of data
    assert len(actual_generation) == 24
    assert len(potential_generation) == 24


def test_generation_exceeds_capacity_constraint(mock_data_provider):
    """Test that generation is capped at capacity even with high historical data."""
    # Create data that exceeds capacity
    capacity = 1000.0
    mock_data_provider.get_data.return_value = pd.DataFrame({
        'wind_generation': [capacity * 1.5] * 24,  # 150% of capacity
        'utc_timestamp': pd.date_range('2024-01-01', periods=24, freq='h')
    })
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=capacity
    )
    
    test_date = datetime.date(2024, 6, 15)
    actual_generation, potential_generation = model.get_generation(test_date)
    
    # All generation should be capped at capacity
    assert all(gen <= capacity for gen in actual_generation)
    assert all(gen == capacity for gen in potential_generation)


def test_get_average_generations_lookback_period_empty_data(mock_data_provider):
    """Test get_average_generations_lookback_period with empty data."""
    mock_data_provider.get_data.return_value = pd.DataFrame()
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0
    )
    
    empty_df = pd.DataFrame()
    result = model.get_average_generations_lookback_period(empty_df)
    
    # Should return default pattern
    assert len(result) == 24
    assert all(isinstance(gen, (int, float)) for gen in result)


def test_get_average_generations_lookback_period_with_data(mock_data_provider):
    """Test get_average_generations_lookback_period with actual data."""
    mock_data_provider.get_data.return_value = pd.DataFrame()
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0
    )
    
    # Create test data with proper datetime index
    test_data = pd.DataFrame({
        'wind_generation': [100.0, 150.0, 200.0, 100.0, 150.0, 200.0],
        'utc_timestamp': [
            datetime.datetime(2024, 1, 1, 0, 0),
            datetime.datetime(2024, 1, 1, 1, 0),
            datetime.datetime(2024, 1, 1, 2, 0),
            datetime.datetime(2024, 1, 2, 0, 0),
            datetime.datetime(2024, 1, 2, 1, 0),
            datetime.datetime(2024, 1, 2, 2, 0),
        ]
    })
    test_data.set_index('utc_timestamp', inplace=True)
    
    result = model.get_average_generations_lookback_period(test_data)
    
    # Should return hourly averages
    assert len(result) == 24
    assert result[0] == 100.0  # Hour 0 average
    assert result[1] == 150.0  # Hour 1 average
    assert result[2] == 200.0  # Hour 2 average
    # Hours 3-23 should be 0.0 (no data)
    assert all(gen == 0.0 for gen in result[3:])


def test_default_pattern_methods(mock_data_provider):
    """Test the default pattern generation methods."""
    mock_data_provider.get_data.return_value = pd.DataFrame()
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0
    )
    
    test_date = datetime.date(2024, 6, 15)
    
    # Test _get_default_pattern_list
    default_list = model._get_default_pattern_list(test_date)
    assert len(default_list) == 24
    assert all(isinstance(gen, (int, float)) for gen in default_list)
    assert all(gen >= 0 for gen in default_list)
    
    # Test _get_default_pattern
    actual_gen, potential_gen = model._get_default_pattern(test_date)
    assert len(actual_gen) == 24
    assert len(potential_gen) == 24
    assert all(gen == model.capacity_kw for gen in potential_gen)
    
    # Test _get_hourly_default
    for hour in range(24):
        hourly_default = model._get_hourly_default(hour, test_date)
        assert isinstance(hourly_default, (int, float))
        assert hourly_default >= 0
        assert hourly_default <= model.capacity_kw
