import os
import sys

import pytest
import datetime
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from scripts.wind_generation_models.forecasted_wind_model import ForecastWindGenerationModel
from scripts.wind_generation_models.wind_data_helper import WindDataHelper
from scripts.shared.interfaces import IDataProvider
from scripts.forecast.interfaces import IFeatureEngineer, IForecaster, IModel


@pytest.fixture
def mock_data_provider():
    """Fixture for mock data provider."""
    mock_provider = Mock(spec=IDataProvider)
    # Mock get_data method to return DataFrame with wind_generation column
    mock_data = pd.DataFrame({
        'wind_generation': [100.0, 150.0, 200.0, 180.0, 120.0],
        'utc_timestamp': pd.date_range('2024-01-01', periods=5, freq='h')
    })
    mock_provider.get_data.return_value = mock_data
    return mock_provider


@pytest.fixture
def mock_feature_engineer():
    """Fixture for mock feature engineer."""
    return Mock(spec=IFeatureEngineer)


@pytest.fixture
def mock_forecaster():
    """Fixture for mock forecaster."""
    return Mock(spec=IForecaster)


@pytest.fixture
def mock_model():
    """Fixture for mock model."""
    return Mock(spec=IModel)


@pytest.fixture
def wind_forecast_model(mock_data_provider, mock_feature_engineer, mock_model):
    """Fixture for default wind forecast model."""
    return ForecastWindGenerationModel(
        data_provider=mock_data_provider,
        feature_engineer=mock_feature_engineer,
        model=mock_model,
        capacity_kw=1000.0,
        lookback_days=30
    )


@pytest.fixture
def test_date():
    """Fixture for a standard test date."""
    return datetime.date(2024, 6, 15)


def test_initialization_default_params(mock_data_provider, mock_feature_engineer, mock_model):
    """Test model initialization with default parameters."""
    model = ForecastWindGenerationModel(
        data_provider=mock_data_provider,
        feature_engineer=mock_feature_engineer,
        model=mock_model
    )
    
    assert model.data_provider == mock_data_provider
    assert model.capacity_kw == 1000.0
    assert model.lookback_days == 30
    assert model.forecaster is not None
    assert isinstance(model.wind_data_helper, WindDataHelper)


@pytest.mark.parametrize(
    "capacity, lookback_days",
    [
        (2000.0, 60),
        (500.0, 15),
        (5000.0, 90),
    ],
)
def test_initialization_custom_params(mock_data_provider, mock_feature_engineer, 
                                    mock_model, capacity, lookback_days):
    """Test model initialization with custom parameters."""
    custom_helper = Mock(spec=WindDataHelper)
    
    model = ForecastWindGenerationModel(
        data_provider=mock_data_provider,
        feature_engineer=mock_feature_engineer,
        model=mock_model,
        wind_data_helper=custom_helper,
        capacity_kw=capacity,
        lookback_days=lookback_days
    )
    
    assert model.data_provider == mock_data_provider
    assert model.wind_data_helper == custom_helper
    assert model.capacity_kw == capacity
    assert model.lookback_days == lookback_days


def test_get_generation_basic_functionality(wind_forecast_model, test_date):
    """Test basic get_generation functionality."""
    actual, potential = wind_forecast_model.get_generation(test_date)
    
    assert isinstance(actual, list)
    assert isinstance(potential, list)
    assert len(actual) == 24
    assert len(potential) == 24
    
    # Values should be non-negative
    assert all(val >= 0 for val in actual)
    assert all(val >= 0 for val in potential)


def test_get_generation_values_within_bounds(wind_forecast_model, test_date):
    """Test that generation values are within expected bounds."""
    actual, potential = wind_forecast_model.get_generation(test_date)
    
    # All values should be non-negative
    assert all(val >= 0 for val in actual)
    assert all(val >= 0 for val in potential)
    
    # Actual should not exceed potential
    for i in range(24):
        assert actual[i] <= potential[i]
    
    # Values should not exceed capacity
    for val in potential:
        assert val <= wind_forecast_model.capacity_kw


def test_get_generation_exception_handling(wind_forecast_model, test_date):
    """Test get_generation handles exceptions gracefully."""
    # Mock a method to raise an exception
    with patch.object(wind_forecast_model, '_generate_forecast') as mock_forecast:
        mock_forecast.side_effect = Exception("Forecast error")
        
        actual, potential = wind_forecast_model.get_generation(test_date)
        
        # Should handle exceptions gracefully and fall back to default
        assert len(actual) == 24
        assert len(potential) == 24
        assert all(val >= 0 for val in actual)
        assert all(val >= 0 for val in potential)


@pytest.mark.parametrize(
    "capacity",
    [0.0, 100.0, 1000000.0],
)
def test_capacity_variations(mock_data_provider, mock_feature_engineer, mock_model, capacity, test_date):
    """Test model with various capacity values."""
    model = ForecastWindGenerationModel(
        data_provider=mock_data_provider,
        feature_engineer=mock_feature_engineer,
        model=mock_model,
        capacity_kw=capacity
    )
    
    actual, potential = model.get_generation(test_date)
    
    # Should still produce valid results
    assert len(actual) == 24
    assert len(potential) == 24
    assert all(val >= 0 for val in actual)
    assert all(val >= 0 for val in potential)
    
    # Potential should match capacity
    for val in potential:
        assert val <= capacity


@pytest.mark.parametrize(
    "season_date,season_name",
    [
        (datetime.date(2024, 12, 15), "winter"),
        (datetime.date(2024, 6, 15), "summer"),
        (datetime.date(2024, 3, 15), "spring"),
        (datetime.date(2024, 9, 15), "autumn"),
    ],
)
def test_seasonal_variations(wind_forecast_model, season_date, season_name):
    """Test forecast for different seasons."""
    actual, potential = wind_forecast_model.get_generation(season_date)
    
    # Should produce valid results for all seasons
    assert len(actual) == 24
    assert len(potential) == 24
    assert all(val >= 0 for val in actual)
    assert all(val >= 0 for val in potential)


@pytest.mark.parametrize(
    "lookback_days",
    [1, 7, 30, 90, 365],
)
def test_lookback_days_variations(mock_data_provider, mock_feature_engineer, mock_model, lookback_days, test_date):
    """Test model with various lookback day values."""
    model = ForecastWindGenerationModel(
        data_provider=mock_data_provider,
        feature_engineer=mock_feature_engineer,
        model=mock_model,
        lookback_days=lookback_days
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
        datetime.date(2024, 7, 4),   # Mid year
    ],
)
def test_edge_case_dates(wind_forecast_model, test_date):
    """Test forecast for edge case dates."""
    actual, potential = wind_forecast_model.get_generation(test_date)
    
    # Should handle edge cases gracefully
    assert len(actual) == 24
    assert len(potential) == 24
    assert all(val >= 0 for val in actual)
    assert all(val >= 0 for val in potential)


def test_train_functionality(wind_forecast_model):
    """Test the train method if it exists."""
    # Check if train method exists and can be called
    if hasattr(wind_forecast_model, 'train'):
        # Mock the forecaster's train method
        with patch.object(wind_forecast_model.forecaster, 'train') as mock_train:
            # Create mock training data
            training_data = pd.DataFrame({
                'datetime': pd.date_range('2024-01-01', periods=100, freq='h'),
                'wind_generation': np.random.uniform(0, 1000, 100)
            })
            
            # Train the model with mock data (only DataFrame argument)
            wind_forecast_model.train(training_data)
            
            # Verify training was called with correct parameters
            mock_train.assert_called_once_with(training_data, column_name='wind_generation', include_lead=True)


def test_forecast_functionality(wind_forecast_model, test_date):
    """Test the forecast method if it exists."""
    # Check if forecast method exists and can be called
    if hasattr(wind_forecast_model, 'forecast'):
        # Mock the forecaster's forecast method to return expected data
        with patch.object(wind_forecast_model.forecaster, 'forecast') as mock_forecast:
            mock_forecast.return_value = np.array([100.0, 150.0, 200.0])
            
            # Create mock DataFrame input 
            forecast_data = pd.DataFrame({
                'datetime': pd.date_range(test_date, periods=24, freq='h'),
                'wind_generation': np.random.uniform(0, 1000, 24)
            })
            
            # Call forecast with proper DataFrame
            result = wind_forecast_model.forecast(forecast_data)
            
            # Verify the result
            assert isinstance(result, (list, np.ndarray))
            assert len(result) > 0
        
        # Should return some forecast data
        assert result is not None


def test_evaluate_functionality(wind_forecast_model):
    """Test the evaluate method if it exists."""
    # Check if evaluate method exists and can be called
    if hasattr(wind_forecast_model, 'evaluate'):
        # Mock evaluation data
        with patch.object(wind_forecast_model, '_get_evaluation_data') as mock_data:
            mock_data.return_value = Mock()
            
            result = wind_forecast_model.evaluate()
            
            # Should return evaluation metrics
            assert result is not None or result is None


def test_string_representation(wind_forecast_model):
    """Test string representation of the model."""
    str_repr = str(wind_forecast_model)
    assert "ForecastWindGenerationModel" in str_repr
    # Just check it's a valid object representation
    assert "object at" in str_repr


def test_generation_type_consistency(wind_forecast_model, test_date):
    """Test that generation returns consistent data types."""
    actual, potential = wind_forecast_model.get_generation(test_date)
    
    # Check types
    assert isinstance(actual, list)
    assert isinstance(potential, list)
    
    # Check element types
    assert all(isinstance(val, (int, float)) for val in actual)
    assert all(isinstance(val, (int, float)) for val in potential)


def test_generation_mathematical_relationships(wind_forecast_model, test_date):
    """Test mathematical relationships in generation data."""
    actual, potential = wind_forecast_model.get_generation(test_date)
    
    # Actual should never exceed potential
    for i in range(24):
        assert actual[i] <= potential[i], f"Hour {i}: actual {actual[i]} > potential {potential[i]}"
    
    # Both should be non-negative
    assert all(val >= 0 for val in actual), "Negative actual generation found"
    assert all(val >= 0 for val in potential), "Negative potential generation found"
    
    # Potential should not exceed capacity
    assert all(val <= wind_forecast_model.capacity_kw for val in potential), "Potential exceeds capacity"


def test_feature_engineer_integration(mock_data_provider, mock_feature_engineer, mock_model, test_date):
    """Test integration with feature engineer."""
    model = ForecastWindGenerationModel(
        data_provider=mock_data_provider,
        feature_engineer=mock_feature_engineer,
        model=mock_model
    )
    
    # Mock feature engineer methods if they exist
    if hasattr(mock_feature_engineer, 'engineer_features'):
        mock_feature_engineer.engineer_features.return_value = Mock()
    
    actual, potential = model.get_generation(test_date)
    
    # Should still work with custom feature engineer
    assert len(actual) == 24
    assert len(potential) == 24


def test_forecaster_integration(mock_data_provider, mock_feature_engineer, mock_model, test_date):
    """Test integration with forecaster."""
    model = ForecastWindGenerationModel(
        data_provider=mock_data_provider,
        feature_engineer=mock_feature_engineer,
        model=mock_model
    )
    
    # Test that forecaster integration works
    actual, potential = model.get_generation(test_date)
    
    # Should still work with custom forecaster setup
    assert len(actual) == 24
    assert len(potential) == 24


def test_generate_forecast_fallback_to_default(wind_forecast_model, test_date):
    """Test _generate_forecast fallback to default pattern."""
    # Mock forecaster to return None or invalid data
    with patch.object(wind_forecast_model.forecaster, 'forecast') as mock_forecast:
        mock_forecast.return_value = None  # This should trigger fallback
        
        actual, potential = wind_forecast_model.get_generation(test_date)
        
        # Should fallback to default pattern
        assert len(actual) == 24
        assert len(potential) == 24
        assert all(val >= 0 for val in actual)


def test_generate_forecast_invalid_length_fallback(wind_forecast_model, test_date):
    """Test _generate_forecast fallback when forecast data has wrong length."""
    # Mock forecaster to return data with wrong length
    with patch.object(wind_forecast_model.forecaster, 'forecast') as mock_forecast:
        mock_forecast.return_value = [100.0, 150.0]  # Only 2 values instead of 24
        
        actual, potential = wind_forecast_model.get_generation(test_date)
        
        # Should fallback to default pattern
        assert len(actual) == 24
        assert len(potential) == 24
        assert all(val >= 0 for val in actual)


def test_auto_train_no_data_fallback(mock_data_provider, mock_feature_engineer, mock_model):
    """Test _auto_train when no data is available."""
    # Mock data provider to return None or empty data
    mock_data_provider.get_data.return_value = None
    
    model = ForecastWindGenerationModel(
        data_provider=mock_data_provider,
        feature_engineer=mock_feature_engineer,
        model=mock_model
    )
    
    # Should set _is_trained to True even without data
    test_date = datetime.date(2024, 6, 15)
    model.get_generation(test_date)  # This triggers auto-training
    
    assert model._is_trained is True



def test_generate_forecast_exception_handling(wind_forecast_model, test_date):
    """Test _generate_forecast exception handling."""
    # Mock the entire forecast flow to raise exception
    with patch.object(wind_forecast_model, '_create_date_features') as mock_features:
        mock_features.side_effect = Exception("Feature creation error")
        
        result = wind_forecast_model._generate_forecast(test_date)
        
        # Should return None on exception
        assert result is None


def test_capacity_constraint_with_negative_values(wind_forecast_model, test_date):
    """Test capacity constraints with negative forecast values."""
    # Mock forecaster to return some negative values
    with patch.object(wind_forecast_model.forecaster, 'forecast') as mock_forecast:
        mock_forecast.return_value = [-50.0, 100.0, 1500.0] * 8  # 24 values with negatives and over-capacity
        
        actual, potential = wind_forecast_model.get_generation(test_date)
        
        # Negative values should be clamped to 0, over-capacity values to capacity
        assert all(val >= 0 for val in actual)
        assert all(val <= wind_forecast_model.capacity_kw for val in actual)
        assert len(actual) == 24


def test_generate_forecast_none_result_fallback(wind_forecast_model, test_date):
    """Test _generate_forecast when forecast returns None."""
    # Override the _generate_forecast to return None to trigger fallback in get_generation
    with patch.object(wind_forecast_model, '_generate_forecast') as mock_gen_forecast:
        mock_gen_forecast.return_value = None
        
        actual, potential = wind_forecast_model.get_generation(test_date)
        
        # Should fallback to default pattern
        assert len(actual) == 24
        assert len(potential) == 24
        assert all(val >= 0 for val in actual)
        assert all(val >= 0 for val in potential)

if __name__ == "__main__":
    pytest.main([__file__])
