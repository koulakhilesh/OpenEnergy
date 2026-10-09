import os
import sys

import pytest
import datetime
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np
import pytz

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from scripts.pv_generation_models.forecasted_pv_model import ForecastPVGenerationModel
from scripts.pv_generation_models.pv_data_helper import PVDataHelper
from scripts.shared.interfaces import IDataProvider
from scripts.forecast.interfaces import IFeatureEngineer, IForecaster, IModel


@pytest.fixture
def mock_data_provider():
    """Fixture for mock data provider."""
    mock_provider = Mock(spec=IDataProvider)
    # Mock get_data method to return DataFrame with pv_generation column
    mock_data = pd.DataFrame({
        'pv_generation': [0.0, 0.0, 50.0, 100.0, 80.0, 0.0],
        'utc_timestamp': pd.date_range('2024-01-01', periods=6, freq='h')
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
def forecast_pv_model(mock_data_provider, mock_feature_engineer, mock_model):
    """Fixture for forecast PV generation model."""
    with patch('scripts.pv_generation_models.forecasted_pv_model.DataPreprocessor') as mock_preprocessor, \
         patch('scripts.pv_generation_models.forecasted_pv_model.TimeSeriesForecaster') as mock_ts_forecaster:
        
        # Mock the preprocessor and forecaster creation
        mock_preprocessor_instance = Mock()
        mock_preprocessor.return_value = mock_preprocessor_instance
        
        mock_forecaster_instance = Mock()
        mock_ts_forecaster.return_value = mock_forecaster_instance
        
        model = ForecastPVGenerationModel(
            data_provider=mock_data_provider,
            feature_engineer=mock_feature_engineer,
            model=mock_model,
            history_length=7 * 24,
            forecast_length=24,
            interpolate=True,
            prior_days=7
        )
        
        # Store mocks for later use
        model._mock_forecaster = mock_forecaster_instance
        model._mock_preprocessor = mock_preprocessor_instance
        
        return model


@pytest.fixture
def sample_pv_data():
    """Fixture for sample PV generation data."""
    dates = pd.date_range('2024-01-01', periods=7*24, freq='h', tz='UTC')
    generations = []
    
    for dt in dates:
        hour = dt.hour
        # Realistic PV generation pattern: 0 at night, peak at noon
        if 6 <= hour <= 18:
            # Bell curve centered at noon (hour 12)
            peak_hour = 12
            distance_from_peak = abs(hour - peak_hour)
            generation = max(0, 100 - (distance_from_peak * 8))
        else:
            generation = 0
        generations.append(generation)
    
    return pd.DataFrame({
        'pv_generation': generations
    }, index=dates)


@pytest.fixture
def test_date():
    """Fixture for a standard test date."""
    return datetime.date(2024, 6, 15)


def test_initialization_default_params(mock_data_provider, mock_feature_engineer, mock_model):
    """Test model initialization with default parameters."""
    with patch('scripts.pv_generation_models.forecasted_pv_model.DataPreprocessor') as mock_preprocessor, \
         patch('scripts.pv_generation_models.forecasted_pv_model.TimeSeriesForecaster') as mock_ts_forecaster:
        
        model = ForecastPVGenerationModel(
            data_provider=mock_data_provider,
            feature_engineer=mock_feature_engineer,
            model=mock_model
        )
        
        assert model.data_provider == mock_data_provider
        assert model.interpolate == True
        assert model._prior_days == 7
        assert isinstance(model.helper, PVDataHelper)
        assert model.GENERATION_COLUMN == "pv_generation"
        assert model.TIMESTAMP_COLUMN == "utc_timestamp"


@pytest.mark.parametrize(
    "history_length, forecast_length, interpolate, prior_days",
    [
        (168, 24, True, 7),
        (336, 48, False, 14),
        (72, 12, True, 3),
        (504, 24, False, 21),
    ],
)
def test_initialization_custom_params(mock_data_provider, mock_feature_engineer, mock_model, 
                                    history_length, forecast_length, interpolate, prior_days):
    """Test model initialization with various custom parameters."""
    with patch('scripts.pv_generation_models.forecasted_pv_model.DataPreprocessor') as mock_preprocessor, \
         patch('scripts.pv_generation_models.forecasted_pv_model.TimeSeriesForecaster') as mock_ts_forecaster:
        
        model = ForecastPVGenerationModel(
            data_provider=mock_data_provider,
            feature_engineer=mock_feature_engineer,
            model=mock_model,
            history_length=history_length,
            forecast_length=forecast_length,
            interpolate=interpolate,
            prior_days=prior_days
        )
        
        assert model.interpolate == interpolate
        assert model._prior_days == prior_days
        
        # Verify DataPreprocessor was called with correct parameters
        mock_preprocessor.assert_called_once_with(
            mock_feature_engineer, history_length, forecast_length
        )


def test_initialization_with_interpolation(mock_data_provider, mock_feature_engineer, mock_model):
    """Test model initialization with interpolation enabled."""
    # Create data with missing values
    test_data = pd.DataFrame({
        'pv_generation': [50.0, None, 100.0, None, 25.0]
    }, index=pd.date_range('2024-01-01', periods=5, freq='h'))
    
    mock_data_provider.get_data.return_value = test_data
    
    with patch('scripts.pv_generation_models.forecasted_pv_model.DataPreprocessor'), \
         patch('scripts.pv_generation_models.forecasted_pv_model.TimeSeriesForecaster'), \
         patch.object(pd.Series, 'interpolate') as mock_interpolate:
        
        model = ForecastPVGenerationModel(
            data_provider=mock_data_provider,
            feature_engineer=mock_feature_engineer,
            model=mock_model,
            interpolate=True
        )
        
        # Should call interpolate when interpolate=True
        mock_interpolate.assert_called_once_with(method="linear")


def test_initialization_without_interpolation(mock_data_provider, mock_feature_engineer, mock_model):
    """Test model initialization with interpolation disabled."""
    test_data = pd.DataFrame({
        'pv_generation': [50.0, None, 100.0, None, 25.0]
    }, index=pd.date_range('2024-01-01', periods=5, freq='h'))
    
    mock_data_provider.get_data.return_value = test_data
    
    with patch('scripts.pv_generation_models.forecasted_pv_model.DataPreprocessor'), \
         patch('scripts.pv_generation_models.forecasted_pv_model.TimeSeriesForecaster'), \
         patch.object(pd.Series, 'interpolate') as mock_interpolate:
        
        model = ForecastPVGenerationModel(
            data_provider=mock_data_provider,
            feature_engineer=mock_feature_engineer,
            model=mock_model,
            interpolate=False
        )
        
        # Should not call interpolate when interpolate=False
        mock_interpolate.assert_not_called()


def test_get_generation_interface_compliance(forecast_pv_model, test_date, sample_pv_data):
    """Test that get_generation method works (interface compliance)."""
    forecast_pv_model.data_provider.get_data.return_value = sample_pv_data
    
    # Mock the forecaster and helper methods
    forecast_pv_model._mock_forecaster.forecast.return_value = np.array([12.0] * 24)
    
    with patch.object(forecast_pv_model.helper, 'get_current_date') as mock_current_date, \
         patch.object(forecast_pv_model.helper, 'get_prior_date') as mock_prior_date, \
         patch.object(forecast_pv_model.helper, 'get_prior_data') as mock_prior_data, \
         patch.object(forecast_pv_model.helper, 'get_current_date_data') as mock_current_data, \
         patch.object(forecast_pv_model.helper, 'get_generation_current_date') as mock_current_gen:
        
        # Setup return values
        mock_current_date.return_value = datetime.datetime(2024, 6, 15, 0, 0, tzinfo=pytz.utc)
        mock_prior_date.return_value = datetime.datetime(2024, 6, 8, 0, 0, tzinfo=pytz.utc)
        mock_prior_data.return_value = sample_pv_data
        mock_current_data.return_value = pd.DataFrame({'pv_generation': [22] * 24})
        mock_current_gen.return_value = [22.0] * 24
        
        # Test get_generation method (interface compliance)
        forecasted_gen, current_gen = forecast_pv_model.get_generation(test_date)
        
        assert isinstance(forecasted_gen, list)
        assert isinstance(current_gen, list)
        assert len(forecasted_gen) == 24
        assert len(current_gen) == 24


def test_get_generations_returns_two_lists(forecast_pv_model, test_date, sample_pv_data):
    """Test that get_generations returns two lists."""
    forecast_pv_model.data_provider.get_data.return_value = sample_pv_data
    
    # Mock the forecaster and helper methods
    forecast_pv_model._mock_forecaster.forecast.return_value = np.array([10.0] * 24)
    
    with patch.object(forecast_pv_model.helper, 'get_current_date') as mock_current_date, \
         patch.object(forecast_pv_model.helper, 'get_prior_date') as mock_prior_date, \
         patch.object(forecast_pv_model.helper, 'get_prior_data') as mock_prior_data, \
         patch.object(forecast_pv_model.helper, 'get_current_date_data') as mock_current_data, \
         patch.object(forecast_pv_model.helper, 'get_generation_current_date') as mock_current_gen:
        
        # Setup return values
        mock_current_date.return_value = datetime.datetime(2024, 6, 15, 0, 0, tzinfo=pytz.utc)
        mock_prior_date.return_value = datetime.datetime(2024, 6, 8, 0, 0, tzinfo=pytz.utc)
        mock_prior_data.return_value = sample_pv_data
        mock_current_data.return_value = pd.DataFrame({'pv_generation': [20] * 24})
        mock_current_gen.return_value = [20.0] * 24
        
        forecasted_gen, current_gen = forecast_pv_model.get_generations(test_date)
        
        assert isinstance(forecasted_gen, list)
        assert isinstance(current_gen, list)
        assert len(forecasted_gen) == 24
        assert len(current_gen) == 24


def test_get_generations_calls_helper_methods(forecast_pv_model, test_date, sample_pv_data):
    """Test that get_generations calls appropriate helper methods."""
    forecast_pv_model.data_provider.get_data.return_value = sample_pv_data
    forecast_pv_model._mock_forecaster.forecast.return_value = np.array([15.0] * 24)
    
    with patch.object(forecast_pv_model.helper, 'get_current_date') as mock_current_date, \
         patch.object(forecast_pv_model.helper, 'get_prior_date') as mock_prior_date, \
         patch.object(forecast_pv_model.helper, 'get_prior_data') as mock_prior_data, \
         patch.object(forecast_pv_model.helper, 'get_current_date_data') as mock_current_data, \
         patch.object(forecast_pv_model.helper, 'get_generation_current_date') as mock_current_gen:
        
        # Setup return values
        mock_current_date.return_value = datetime.datetime(2024, 6, 15, 0, 0, tzinfo=pytz.utc)
        mock_prior_date.return_value = datetime.datetime(2024, 6, 8, 0, 0, tzinfo=pytz.utc)
        mock_prior_data.return_value = sample_pv_data
        mock_current_data.return_value = pd.DataFrame({'pv_generation': [25] * 24})
        mock_current_gen.return_value = [25.0] * 24
        
        forecasted_gen, current_gen = forecast_pv_model.get_generations(test_date)
        
        # Verify helper methods were called
        mock_current_date.assert_called_once_with(test_date)
        mock_prior_date.assert_called_once()
        mock_prior_data.assert_called_once()
        mock_current_data.assert_called_once()
        mock_current_gen.assert_called_once()


def test_train_functionality(forecast_pv_model, sample_pv_data):
    """Test the train method functionality."""
    forecast_pv_model.train(sample_pv_data)
    
    # Verify that the forecaster's train method was called with correct parameters
    forecast_pv_model._mock_forecaster.train.assert_called_once_with(
        sample_pv_data, 
        column_name="pv_generation", 
        include_lead=True
    )


def test_forecast_functionality(forecast_pv_model, sample_pv_data):
    """Test the forecast method functionality."""
    # Mock the forecaster to return a numpy array
    expected_forecast = np.array([[10.0], [20.0], [30.0], [40.0]])
    forecast_pv_model._mock_forecaster.forecast.return_value = expected_forecast
    
    result = forecast_pv_model.forecast(sample_pv_data)
    
    # Verify the forecaster was called correctly
    forecast_pv_model._mock_forecaster.forecast.assert_called_once_with(
        sample_pv_data,
        column_name="pv_generation",
        include_lead=False
    )
    
    # Verify the result is flattened and converted to list
    assert isinstance(result, list)
    assert result == [10.0, 20.0, 30.0, 40.0]


def test_evaluate_functionality(forecast_pv_model):
    """Test the evaluate method functionality."""
    y_true = np.array([10, 20, 30, 40])
    y_pred = np.array([12, 18, 32, 38])
    expected_score = 0.95
    
    forecast_pv_model._mock_forecaster.evaluate.return_value = expected_score
    
    result = forecast_pv_model.evaluate(y_true, y_pred)
    
    # Verify the forecaster's evaluate method was called
    forecast_pv_model._mock_forecaster.evaluate.assert_called_once_with(y_true, y_pred)
    assert result == expected_score


def test_save_model_functionality(forecast_pv_model):
    """Test the save_model method functionality."""
    file_path = "/tmp/test_model.pkl"
    
    forecast_pv_model.save_model(file_path)
    
    # Verify the forecaster's save_model method was called
    forecast_pv_model._mock_forecaster.save_model.assert_called_once_with(file_path)


def test_load_model_functionality():
    """Test the load_model static method functionality."""
    file_path = "/tmp/test_model.pkl"
    expected_model = Mock()
    
    with patch('scripts.pv_generation_models.forecasted_pv_model.TimeSeriesForecaster') as mock_ts_forecaster:
        mock_ts_forecaster.load_model.return_value = expected_model
        
        result = ForecastPVGenerationModel.load_model(file_path)
        
        # Verify the TimeSeriesForecaster's load_model method was called
        mock_ts_forecaster.load_model.assert_called_once_with(file_path)
        assert result == expected_model


def test_constants_values(forecast_pv_model):
    """Test that class constants have expected values."""
    assert forecast_pv_model.DAYS_IN_WEEK == 7
    assert forecast_pv_model.GENERATION_COLUMN == "pv_generation"
    assert forecast_pv_model.TIMESTAMP_COLUMN == "utc_timestamp"


def test_data_provider_integration(mock_data_provider, mock_feature_engineer, mock_model):
    """Test integration with data provider."""
    expected_data = pd.DataFrame({
        'pv_generation': [25.0, 50.0, 75.0]
    }, index=pd.date_range('2024-01-01', periods=3, freq='h'))
    
    mock_data_provider.get_data.return_value = expected_data
    
    with patch('scripts.pv_generation_models.forecasted_pv_model.DataPreprocessor'), \
         patch('scripts.pv_generation_models.forecasted_pv_model.TimeSeriesForecaster'):
        
        model = ForecastPVGenerationModel(
            data_provider=mock_data_provider,
            feature_engineer=mock_feature_engineer,
            model=mock_model
        )
        
        # Verify get_data was called with correct parameters
        mock_data_provider.get_data.assert_called_once_with(
            column_names=['pv_generation'],
            timestamp_column='utc_timestamp'
        )
        
        # Verify data is stored correctly
        pd.testing.assert_frame_equal(model.data, expected_data)


@pytest.mark.parametrize(
    "test_date",
    [
        datetime.date(2024, 1, 1),   # New Year
        datetime.date(2024, 6, 21),  # Summer solstice
        datetime.date(2024, 12, 21), # Winter solstice
        datetime.date(2024, 2, 29),  # Leap year
    ],
)
def test_get_generations_various_dates(forecast_pv_model, test_date, sample_pv_data):
    """Test get_generations with various dates."""
    forecast_pv_model.data_provider.get_data.return_value = sample_pv_data
    forecast_pv_model._mock_forecaster.forecast.return_value = np.array([15.0] * 24)
    
    with patch.object(forecast_pv_model.helper, 'get_current_date') as mock_current_date, \
         patch.object(forecast_pv_model.helper, 'get_prior_date') as mock_prior_date, \
         patch.object(forecast_pv_model.helper, 'get_prior_data') as mock_prior_data, \
         patch.object(forecast_pv_model.helper, 'get_current_date_data') as mock_current_data, \
         patch.object(forecast_pv_model.helper, 'get_generation_current_date') as mock_current_gen:
        
        # Setup return values to avoid timezone comparisons
        mock_current_date.return_value = datetime.datetime(2024, 6, 15, 0, 0, tzinfo=pytz.utc)
        mock_prior_date.return_value = datetime.datetime(2024, 6, 8, 0, 0, tzinfo=pytz.utc)
        mock_prior_data.return_value = sample_pv_data
        mock_current_data.return_value = pd.DataFrame({'pv_generation': [25] * 24})
        mock_current_gen.return_value = [25.0] * 24
        
        forecasted_gen, current_gen = forecast_pv_model.get_generations(test_date)
        
        assert len(forecasted_gen) == 24
        assert len(current_gen) == 24
        assert all(isinstance(val, (int, float)) for val in forecasted_gen)
        assert all(isinstance(val, (int, float)) for val in current_gen)


def test_realistic_pv_forecast_integration(mock_data_provider, mock_feature_engineer, mock_model, test_date):
    """Test integration with realistic PV forecasting flow."""
    # Create realistic PV data for multiple days including the test date
    start_date = datetime.datetime(2024, 6, 8, 0, 0, tzinfo=pytz.utc)
    end_date = datetime.datetime(2024, 6, 16, 0, 0, tzinfo=pytz.utc)
    dates = pd.date_range(start_date, end_date, freq='h', inclusive='left')
    
    # Simulate realistic PV generation pattern
    generations = []
    for dt in dates:
        hour = dt.hour
        if 6 <= hour <= 18:
            peak_hour = 12
            distance_from_peak = abs(hour - peak_hour)
            generation = max(0, 100 - (distance_from_peak * 8))
        else:
            generation = 0
        generations.append(generation)
    
    pv_data = pd.DataFrame({
        'pv_generation': generations
    }, index=dates)
    
    mock_data_provider.get_data.return_value = pv_data
    
    with patch('scripts.pv_generation_models.forecasted_pv_model.DataPreprocessor'), \
         patch('scripts.pv_generation_models.forecasted_pv_model.TimeSeriesForecaster') as mock_ts_forecaster:
        
        mock_forecaster_instance = Mock()
        mock_ts_forecaster.return_value = mock_forecaster_instance
        
        # Mock realistic forecast
        realistic_forecast = np.array([0] * 6 + [20, 40, 60, 80, 100, 80, 60, 40, 20] + [0] * 9)
        mock_forecaster_instance.forecast.return_value = realistic_forecast
        
        model = ForecastPVGenerationModel(
            data_provider=mock_data_provider,
            feature_engineer=mock_feature_engineer,
            model=mock_model
        )
        
        # This should work end-to-end
        forecasted_gen, current_gen = model.get_generations(test_date)
        
        assert isinstance(forecasted_gen, list)
        assert isinstance(current_gen, list)
        assert len(forecasted_gen) == 24
        assert len(current_gen) == 24
        
        # Verify that we get reasonable PV patterns for forecast
        # Night hours should have low/zero generation
        assert forecasted_gen[0] == 0  # Midnight
        assert forecasted_gen[23] == 0  # 11 PM
        
        # Day hours should have higher generation in forecast
        assert forecasted_gen[12] > forecasted_gen[6]  # Noon > 6 AM
        assert forecasted_gen[12] > forecasted_gen[18]  # Noon > 6 PM
        
        # All values should be non-negative
        assert all(val >= 0 for val in forecasted_gen)
        assert all(val >= 0 for val in current_gen)


@pytest.mark.parametrize(
    "interpolate_flag",
    [True, False],
)
def test_interpolation_behavior(mock_data_provider, mock_feature_engineer, mock_model, interpolate_flag):
    """Test model behavior with and without interpolation."""
    test_data = pd.DataFrame({
        'pv_generation': [50.0, None, 100.0, None, 25.0]
    }, index=pd.date_range('2024-01-01', periods=5, freq='h'))
    
    mock_data_provider.get_data.return_value = test_data
    
    with patch('scripts.pv_generation_models.forecasted_pv_model.DataPreprocessor'), \
         patch('scripts.pv_generation_models.forecasted_pv_model.TimeSeriesForecaster'):
        
        model = ForecastPVGenerationModel(
            data_provider=mock_data_provider,
            feature_engineer=mock_feature_engineer,
            model=mock_model,
            interpolate=interpolate_flag
        )
        
        assert model.interpolate == interpolate_flag


def test_edge_case_dates(forecast_pv_model, sample_pv_data):
    """Test model with edge case dates."""
    edge_dates = [
        datetime.date(2024, 2, 29),  # Leap year
        datetime.date(2024, 12, 31), # Year end
        datetime.date(2024, 1, 1),   # Year start
        datetime.date(2000, 1, 1),   # Different year
    ]
    
    forecast_pv_model.data_provider.get_data.return_value = sample_pv_data
    forecast_pv_model._mock_forecaster.forecast.return_value = np.array([15.0] * 24)
    
    for test_date in edge_dates:
        with patch.object(forecast_pv_model.helper, 'get_current_date') as mock_current_date, \
             patch.object(forecast_pv_model.helper, 'get_prior_date') as mock_prior_date, \
             patch.object(forecast_pv_model.helper, 'get_prior_data') as mock_prior_data, \
             patch.object(forecast_pv_model.helper, 'get_current_date_data') as mock_current_data, \
             patch.object(forecast_pv_model.helper, 'get_generation_current_date') as mock_current_gen:
            
            # Setup return values to avoid timezone comparisons
            mock_current_date.return_value = datetime.datetime(test_date.year, test_date.month, test_date.day, 0, 0, tzinfo=pytz.utc)
            prior_date_dt = datetime.datetime(test_date.year, test_date.month, test_date.day, 0, 0, tzinfo=pytz.utc) - datetime.timedelta(days=7)
            mock_prior_date.return_value = prior_date_dt
            mock_prior_data.return_value = sample_pv_data
            mock_current_data.return_value = pd.DataFrame({'pv_generation': [25] * 24})
            mock_current_gen.return_value = [25.0] * 24
            
            forecasted_gen, current_gen = forecast_pv_model.get_generations(test_date)
            
            assert len(forecasted_gen) == 24
            assert len(current_gen) == 24
            assert all(val >= 0 for val in forecasted_gen)
            assert all(val >= 0 for val in current_gen)


if __name__ == "__main__":
    pytest.main([__file__])
