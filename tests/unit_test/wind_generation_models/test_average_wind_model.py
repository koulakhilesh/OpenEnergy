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


def test_get_generation_fallback_to_default_pattern(mock_data_provider, test_date):
    """Test get_generation falls back to default pattern when no data available."""
    # Set up empty data
    mock_data_provider.get_data.return_value = pd.DataFrame()
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0,
        lookback_days=30
    )
    
    actual_gen, potential_gen = model.get_generation(test_date)
    
    # Should return default pattern, not empty
    assert len(actual_gen) == 24
    assert len(potential_gen) == 24
    assert all(gen >= 0 for gen in actual_gen)
    assert all(gen == 1000.0 for gen in potential_gen)


def test_get_generation_empty_current_date_data(mock_data_provider, test_date):
    """Test get_generation when current date data is empty."""
    # Create historical data but no data for current date
    dates = pd.date_range('2024-06-01', periods=24*7, freq='h')  # Week of data, not including test_date
    historical_data = pd.DataFrame({
        'wind_generation': [200.0] * len(dates)
    }, index=dates)
    
    mock_data_provider.get_data.return_value = historical_data
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0,
        lookback_days=30
    )
    
    actual_gen, potential_gen = model.get_generation(test_date)
    
    # Should use average generations since no current date data
    assert len(actual_gen) == 24
    assert len(potential_gen) == 24
    assert all(gen >= 0 for gen in actual_gen)


def test_get_generation_current_data_wrong_length(mock_data_provider, test_date):
    """Test get_generation when current date data has wrong length."""
    # Create data including current date but with wrong hourly length
    dates = pd.date_range('2024-06-15', periods=12, freq='h')  # Only 12 hours instead of 24
    current_date_data = pd.DataFrame({
        'wind_generation': [300.0] * len(dates)
    }, index=dates)
    
    # Also create some historical data for averages
    hist_dates = pd.date_range('2024-06-01', periods=24*7, freq='h')
    historical_data = pd.DataFrame({
        'wind_generation': [200.0] * len(hist_dates)
    }, index=hist_dates)
    
    # Combine the data
    all_data = pd.concat([historical_data, current_date_data])
    mock_data_provider.get_data.return_value = all_data
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0,
        lookback_days=30
    )
    
    actual_gen, potential_gen = model.get_generation(test_date)
    
    # Should fall back to average generations since current data length != 24
    assert len(actual_gen) == 24
    assert len(potential_gen) == 24


def test_get_generation_exception_handling(mock_data_provider, test_date):
    """Test get_generation exception handling when processing current date data."""
    # Create valid data but mock an exception in get_current_date_data
    dates = pd.date_range('2024-06-01', periods=24*7, freq='h')
    data = pd.DataFrame({
        'wind_generation': [200.0] * len(dates)
    }, index=dates)
    
    mock_data_provider.get_data.return_value = data
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0,
        lookback_days=30
    )
    
    # Mock get_current_date_data to raise an exception
    with patch.object(model.wind_data_helper, 'get_current_date_data') as mock_current:
        mock_current.side_effect = Exception("Simulated error")
        
        actual_gen, potential_gen = model.get_generation(test_date)
        
        # Should fall back to average generations due to exception
        assert len(actual_gen) == 24
        assert len(potential_gen) == 24
        assert all(gen >= 0 for gen in actual_gen)


def test_get_generation_full_exception_fallback(mock_data_provider, test_date):
    """Test get_generation falls back to default pattern on any major exception."""
    # Initialize model with valid data first
    mock_data_provider.get_data.return_value = pd.DataFrame()
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0,
        lookback_days=30
    )
    
    # Now mock a major exception in get_generation method by patching wind_data_helper methods
    with patch.object(model.wind_data_helper, 'get_current_date') as mock_current:
        mock_current.side_effect = Exception("Major system error")
        
        actual_gen, potential_gen = model.get_generation(test_date)
        
        # Should return default pattern tuple
        assert len(actual_gen) == 24
        assert len(potential_gen) == 24
        assert all(gen >= 0 for gen in actual_gen)
        assert all(gen == 1000.0 for gen in potential_gen)


def test_get_generation_valid_current_data_24_hours(mock_data_provider, test_date):
    """Test get_generation with valid current date data (exactly 24 hours)."""
    # Create current date data with exactly 24 hours
    current_dates = pd.date_range('2024-06-15', periods=24, freq='h')
    current_data = pd.DataFrame({
        'wind_generation': [400.0] * 24  # Current generation
    }, index=current_dates)
    
    # Also create historical data for averages
    hist_dates = pd.date_range('2024-06-01', periods=24*7, freq='h')
    historical_data = pd.DataFrame({
        'wind_generation': [200.0] * len(hist_dates)
    }, index=hist_dates)
    
    # Combine the data
    all_data = pd.concat([historical_data, current_data])
    mock_data_provider.get_data.return_value = all_data
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0,
        lookback_days=30
    )
    
    actual_gen, potential_gen = model.get_generation(test_date)
    
    # Should use current data since it has exactly 24 hours
    assert len(actual_gen) == 24
    assert len(potential_gen) == 24
    # After seasonal adjustment, should be close to but not exactly 400
    assert all(gen > 0 for gen in actual_gen)
    assert all(gen <= 1000.0 for gen in actual_gen)  # Shouldn't exceed capacity


def test_get_average_generations_lookback_period_empty_data(wind_model):
    """Test get_average_generations_lookback_period with empty DataFrame."""
    empty_data = pd.DataFrame()
    
    result = wind_model.get_average_generations_lookback_period(empty_data)
    
    # Should return default pattern list
    assert isinstance(result, list)
    assert len(result) == 24
    assert all(gen >= 0 for gen in result)


def test_get_average_generations_lookback_period_assertion_check(wind_model):
    """Test get_average_generations_lookback_period DatetimeIndex assertion."""
    # Create data with DatetimeIndex to trigger assertion
    dates = pd.date_range('2024-06-01', periods=24, freq='h')
    data = pd.DataFrame({
        'wind_generation': [150.0] * 24
    }, index=dates)
    
    result = wind_model.get_average_generations_lookback_period(data)
    
    # Should execute assertion and return grouped averages
    assert isinstance(result, list)
    assert len(result) == 24
    assert all(gen >= 0 for gen in result)


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


def test_seasonal_adjustment_coverage(mock_data_provider, test_date):
    """Test seasonal adjustment is applied in get_generation."""
    # Create winter date to test seasonal adjustment
    winter_date = datetime.date(2024, 1, 15)
    
    dates = pd.date_range('2024-01-01', periods=24*7, freq='h')
    data = pd.DataFrame({
        'wind_generation': [300.0] * len(dates)
    }, index=dates)
    
    mock_data_provider.get_data.return_value = data
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0,
        lookback_days=30
    )
    
    actual_gen, potential_gen = model.get_generation(winter_date)
    
    # Winter should have higher generation due to seasonal factor
    assert len(actual_gen) == 24
    assert len(potential_gen) == 24
    assert all(gen >= 0 for gen in actual_gen)


def test_capacity_limit_enforcement(mock_data_provider, test_date):
    """Test that generation is capped at capacity limit."""
    # Create data with very high generation values
    dates = pd.date_range('2024-06-15', periods=24, freq='h')
    high_generation_data = pd.DataFrame({
        'wind_generation': [1500.0] * 24  # Above capacity
    }, index=dates)
    
    mock_data_provider.get_data.return_value = high_generation_data
    
    model = HistoricalAverageWindGenerationModel(
        data_provider=mock_data_provider,
        capacity_kw=1000.0,
        lookback_days=30
    )
    
    actual_gen, potential_gen = model.get_generation(test_date)
    
    # All actual generation should be capped at capacity
    assert all(gen <= 1000.0 for gen in actual_gen)
    assert all(gen == 1000.0 for gen in potential_gen)


if __name__ == "__main__":
    pytest.main([__file__])
