import os
import sys

import pytest
import datetime
from unittest.mock import Mock, patch
import pandas as pd
import pytz

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from scripts.pv_generation_models.average_pv_model import HistoricalAveragePVGenerationModel
from scripts.pv_generation_models.pv_data_helper import PVDataHelper
from scripts.shared.interfaces import IDataProvider


@pytest.fixture
def mock_data_provider():
    """Fixture for mock data provider."""
    return Mock(spec=IDataProvider)


@pytest.fixture
def pv_model(mock_data_provider):
    """Fixture for default PV generation model."""
    # Mock the data provider to return empty DataFrame initially
    mock_data_provider.get_data.return_value = pd.DataFrame(
        columns=['pv_generation'], 
        index=pd.DatetimeIndex([], tz='UTC')
    )
    return HistoricalAveragePVGenerationModel(
        data_provider=mock_data_provider,
        interpolate=True,
        prior_days=7
    )


@pytest.fixture
def pv_model_custom(mock_data_provider):
    """Fixture for custom PV generation model."""
    mock_data_provider.get_data.return_value = pd.DataFrame(
        columns=['pv_generation'], 
        index=pd.DatetimeIndex([], tz='UTC')
    )
    return HistoricalAveragePVGenerationModel(
        data_provider=mock_data_provider,
        interpolate=False,
        prior_days=14
    )


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

def test_initialization_default_params(mock_data_provider):
    """Test model initialization with default parameters."""
    mock_data_provider.get_data.return_value = pd.DataFrame(
        columns=['pv_generation'], 
        index=pd.DatetimeIndex([], tz='UTC')
    )
    
    model = HistoricalAveragePVGenerationModel(data_provider=mock_data_provider)
    
    assert model.data_provider == mock_data_provider
    assert model.interpolate == True
    assert model.prior_days == 7
    assert isinstance(model.helper, PVDataHelper)
    assert model.GENERATION_COLUMN == "pv_generation"
    assert model.TIMESTAMP_COLUMN == "utc_timestamp"


@pytest.mark.parametrize(
    "interpolate, prior_days",
    [
        (True, 7),
        (False, 14),
        (True, 30),
        (False, 5),
    ],
)
def test_initialization_custom_params(mock_data_provider, interpolate, prior_days):
    """Test model initialization with various custom parameters."""
    mock_data_provider.get_data.return_value = pd.DataFrame(
        columns=['pv_generation'], 
        index=pd.DatetimeIndex([], tz='UTC')
    )
    
    model = HistoricalAveragePVGenerationModel(
        data_provider=mock_data_provider,
        interpolate=interpolate,
        prior_days=prior_days
    )
    
    assert model.interpolate == interpolate
    assert model.prior_days == prior_days


def test_initialization_with_interpolation(mock_data_provider):
    """Test model initialization with interpolation enabled."""
    # Create data with missing values
    test_data = pd.DataFrame({
        'pv_generation': [50.0, None, 100.0]
    }, index=pd.date_range('2024-01-01', periods=3, freq='h'))
    
    mock_data_provider.get_data.return_value = test_data
    
    with patch.object(pd.Series, 'interpolate') as mock_interpolate:
        model = HistoricalAveragePVGenerationModel(
            data_provider=mock_data_provider,
            interpolate=True
        )
        
        # Should call interpolate when interpolate=True
        mock_interpolate.assert_called_once_with(method="linear")


def test_initialization_without_interpolation(mock_data_provider):
    """Test model initialization with interpolation disabled."""
    test_data = pd.DataFrame({
        'pv_generation': [50.0, None, 100.0]
    }, index=pd.date_range('2024-01-01', periods=3, freq='h'))
    
    mock_data_provider.get_data.return_value = test_data
    
    with patch.object(pd.Series, 'interpolate') as mock_interpolate:
        model = HistoricalAveragePVGenerationModel(
            data_provider=mock_data_provider,
            interpolate=False
        )
        
        # Should not call interpolate when interpolate=False
        mock_interpolate.assert_not_called()


def test_get_generation_returns_two_lists(pv_model, test_date, sample_pv_data):
    """Test that get_generation returns two lists."""
    pv_model.data_provider.get_data.return_value = sample_pv_data
    
    with patch.object(pv_model, 'get_average_generations_last_week') as mock_avg, \
         patch.object(pv_model.helper, 'get_generation_current_date') as mock_current:
        
        mock_avg.return_value = [10.0] * 24
        mock_current.return_value = [20.0] * 24
        
        avg_gen, current_gen = pv_model.get_generation(test_date)
        
        assert isinstance(avg_gen, list)
        assert isinstance(current_gen, list)
        assert len(avg_gen) == 24
        assert len(current_gen) == 24


def test_get_generation_calls_helper_methods(pv_model, test_date, sample_pv_data):
    """Test that get_generation calls appropriate helper methods."""
    pv_model.data_provider.get_data.return_value = sample_pv_data
    
    with patch.object(pv_model.helper, 'get_current_date') as mock_current_date, \
         patch.object(pv_model.helper, 'get_prior_date') as mock_prior_date, \
         patch.object(pv_model.helper, 'get_prior_data') as mock_prior_data, \
         patch.object(pv_model.helper, 'get_current_date_data') as mock_current_data, \
         patch.object(pv_model.helper, 'get_generation_current_date') as mock_current_gen, \
         patch.object(pv_model, 'get_average_generations_last_week') as mock_avg:
        
        # Setup return values
        mock_current_date.return_value = datetime.datetime(2024, 6, 15, 0, 0, tzinfo=pytz.utc)
        mock_prior_date.return_value = datetime.datetime(2024, 6, 8, 0, 0, tzinfo=pytz.utc)
        mock_prior_data.return_value = sample_pv_data
        mock_current_data.return_value = pd.DataFrame({'pv_generation': [0] * 24})
        mock_current_gen.return_value = [0] * 24
        mock_avg.return_value = [10] * 24
        
        avg_gen, current_gen = pv_model.get_generation(test_date)
        
        # Verify helper methods were called
        mock_current_date.assert_called_once_with(test_date)
        mock_prior_date.assert_called_once()
        mock_prior_data.assert_called_once()
        mock_current_data.assert_called_once()
        mock_current_gen.assert_called_once()
        mock_avg.assert_called_once()


@pytest.mark.parametrize(
    "test_date",
    [
        datetime.date(2024, 1, 1),   # New Year
        datetime.date(2024, 6, 21),  # Summer solstice
        datetime.date(2024, 12, 21), # Winter solstice
        datetime.date(2024, 2, 29),  # Leap year
    ],
)
def test_get_generation_various_dates(pv_model, test_date, sample_pv_data):
    """Test get_generation with various dates."""
    pv_model.data_provider.get_data.return_value = sample_pv_data
    
    with patch.object(pv_model.helper, 'get_current_date') as mock_current_date, \
         patch.object(pv_model.helper, 'get_prior_date') as mock_prior_date, \
         patch.object(pv_model.helper, 'get_prior_data') as mock_prior_data, \
         patch.object(pv_model.helper, 'get_current_date_data') as mock_current_data, \
         patch.object(pv_model.helper, 'get_generation_current_date') as mock_current_gen, \
         patch.object(pv_model, 'get_average_generations_last_week') as mock_avg:
        
        # Setup return values to avoid timezone comparisons
        mock_current_date.return_value = datetime.datetime(2024, 6, 15, 0, 0, tzinfo=pytz.utc)
        mock_prior_date.return_value = datetime.datetime(2024, 6, 8, 0, 0, tzinfo=pytz.utc)
        mock_prior_data.return_value = sample_pv_data
        mock_current_data.return_value = pd.DataFrame({'pv_generation': [25] * 24})
        mock_avg.return_value = [15.0] * 24
        mock_current_gen.return_value = [25.0] * 24
        
        avg_gen, current_gen = pv_model.get_generation(test_date)
        
        assert len(avg_gen) == 24
        assert len(current_gen) == 24
        assert all(isinstance(val, (int, float)) for val in avg_gen)
        assert all(isinstance(val, (int, float)) for val in current_gen)

def test_get_average_generations_last_week_empty_data(pv_model):
    """Test get_average_generations_last_week with empty data."""
    # Create empty DataFrame with DatetimeIndex
    empty_data = pd.DataFrame(columns=['pv_generation'])
    empty_data.index = pd.DatetimeIndex([])
    
    result = pv_model.get_average_generations_last_week(empty_data)
    
    assert isinstance(result, list)
    assert len(result) == 0


def test_get_average_generations_last_week_with_data(pv_model):
    """Test get_average_generations_last_week with actual data."""
    # Create sample data with multiple days
    dates = []
    generations = []
    
    # Create 3 days of hourly data
    for day in range(3):
        for hour in range(24):
            dates.append(datetime.datetime(2024, 1, day + 1, hour, 0, tzinfo=pytz.utc))
            # Simulate PV generation: 0 at night, peak at noon
            if 6 <= hour <= 18:
                generations.append(hour * 10 if hour <= 12 else (24 - hour) * 10)
            else:
                generations.append(0)
    
    test_data = pd.DataFrame({
        'pv_generation': generations
    }, index=pd.DatetimeIndex(dates))
    
    result = pv_model.get_average_generations_last_week(test_data)
    
    assert isinstance(result, list)
    assert len(result) == 24  # Should have 24 hourly averages
    
    # Check that night hours (0-5, 19-23) have 0 generation
    for hour in [0, 1, 2, 3, 4, 5, 19, 20, 21, 22, 23]:
        assert result[hour] == 0
    
    # Check that day hours have positive generation
    for hour in range(6, 19):
        assert result[hour] > 0


@pytest.mark.parametrize(
    "num_days, expected_length",
    [
        (1, 24),
        (3, 24),
        (7, 24),
        (14, 24),
    ],
)
def test_get_average_generations_last_week_various_periods(pv_model, num_days, expected_length):
    """Test get_average_generations_last_week with various time periods."""
    # Create data for specified number of days
    dates = []
    generations = []
    
    for day in range(num_days):
        for hour in range(24):
            dates.append(datetime.datetime(2024, 1, day + 1, hour, 0, tzinfo=pytz.utc))
            # Simple pattern: higher during day hours
            generations.append(hour * 5 if 6 <= hour <= 18 else 0)
    
    test_data = pd.DataFrame({
        'pv_generation': generations
    }, index=pd.DatetimeIndex(dates))
    
    result = pv_model.get_average_generations_last_week(test_data)
    
    assert isinstance(result, list)
    assert len(result) == expected_length


def test_get_average_generations_last_week_single_day(pv_model):
    """Test get_average_generations_last_week with single day data."""
    # Create single day data
    dates = [datetime.datetime(2024, 1, 1, hour, 0, tzinfo=pytz.utc) for hour in range(24)]
    generations = [hour * 5 if 6 <= hour <= 18 else 0 for hour in range(24)]
    
    test_data = pd.DataFrame({
        'pv_generation': generations
    }, index=pd.DatetimeIndex(dates))
    
    result = pv_model.get_average_generations_last_week(test_data)
    
    assert isinstance(result, list)
    assert len(result) == 24
    
    # Since there's only one day, averages should equal the single day values
    for hour in range(24):
        assert result[hour] == generations[hour]


def test_get_average_generations_last_week_assertion_error(pv_model):
    """Test that get_average_generations_last_week raises assertion error for non-DatetimeIndex."""
    # Create DataFrame with non-DatetimeIndex
    test_data = pd.DataFrame({
        'pv_generation': [10, 20, 30]
    }, index=[0, 1, 2])
    
    with pytest.raises(AssertionError):
        pv_model.get_average_generations_last_week(test_data)


def test_pv_generation_daily_pattern(pv_model, sample_pv_data):
    """Test that PV generation follows expected daily patterns."""
    result = pv_model.get_average_generations_last_week(sample_pv_data)
    
    assert isinstance(result, list)
    assert len(result) == 24
    
    # Night hours should have zero generation
    assert result[0] == 0   # Midnight
    assert result[4] == 0   # 4 AM
    assert result[23] == 0  # 11 PM
    
    # Day hours should have positive generation
    assert result[12] > 0   # Noon should have highest
    assert result[10] > 0   # Morning
    assert result[15] > 0   # Afternoon
    
    # Peak should be around noon
    peak_hour = result.index(max(result))
    assert 10 <= peak_hour <= 14  # Peak between 10 AM and 2 PM


@pytest.mark.parametrize(
    "generation_values, expected_pattern",
    [
        ([100] * 24, "constant"),
        ([0] * 12 + [50] * 12, "half_day"),
        ([i for i in range(24)], "linear_increase"),
    ],
)
def test_get_average_generations_last_week_patterns(pv_model, generation_values, expected_pattern):
    """Test get_average_generations_last_week with different generation patterns."""
    dates = [datetime.datetime(2024, 1, 1, hour, 0, tzinfo=pytz.utc) for hour in range(24)]
    
    test_data = pd.DataFrame({
        'pv_generation': generation_values
    }, index=pd.DatetimeIndex(dates))
    
    result = pv_model.get_average_generations_last_week(test_data)
    
    assert isinstance(result, list)
    assert len(result) == 24
    
    if expected_pattern == "constant":
        assert all(val == 100 for val in result)
    elif expected_pattern == "half_day":
        assert all(val == 0 for val in result[:12])
        assert all(val == 50 for val in result[12:])
    elif expected_pattern == "linear_increase":
        for i in range(24):
            assert result[i] == i


def test_constants_values(pv_model):
    """Test that class constants have expected values."""
    assert pv_model.DAYS_IN_WEEK == 7
    assert pv_model.GENERATION_COLUMN == "pv_generation"
    assert pv_model.TIMESTAMP_COLUMN == "utc_timestamp"


def test_data_provider_integration(mock_data_provider):
    """Test integration with data provider."""
    expected_data = pd.DataFrame({
        'pv_generation': [25.0, 50.0, 75.0]
    }, index=pd.date_range('2024-01-01', periods=3, freq='h'))
    
    mock_data_provider.get_data.return_value = expected_data
    
    model = HistoricalAveragePVGenerationModel(data_provider=mock_data_provider)
    
    # Verify get_data was called with correct parameters
    mock_data_provider.get_data.assert_called_once_with(
        column_names=['pv_generation'],
        timestamp_column='utc_timestamp'
    )
    
    # Verify data is stored correctly
    pd.testing.assert_frame_equal(model.data, expected_data)


def test_realistic_pv_data_integration(mock_data_provider, test_date):
    """Test integration with realistic PV data flow."""
    # Create realistic PV data for multiple days including the test date
    start_date = datetime.datetime(2024, 6, 8, 0, 0, tzinfo=pytz.utc)
    # Include data up to and including the test date (2024-06-15)
    end_date = datetime.datetime(2024, 6, 16, 0, 0, tzinfo=pytz.utc)
    dates = pd.date_range(start_date, end_date, freq='h', inclusive='left')
    
    # Simulate realistic PV generation pattern
    generations = []
    for dt in dates:
        hour = dt.hour
        # PV generation follows a daily pattern
        if 6 <= hour <= 18:
            # Peak at noon (hour 12)
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
    
    model = HistoricalAveragePVGenerationModel(data_provider=mock_data_provider)
    
    # This should work end-to-end
    avg_gen, current_gen = model.get_generation(test_date)
    
    assert isinstance(avg_gen, list)
    assert isinstance(current_gen, list)
    assert len(avg_gen) == 24
    assert len(current_gen) == 24
    
    # Verify that we get reasonable PV patterns
    # Night hours should have low/zero generation
    assert avg_gen[0] == 0  # Midnight
    assert avg_gen[23] == 0  # 11 PM
    
    # Day hours should have higher generation
    assert avg_gen[12] > avg_gen[6]  # Noon > 6 AM
    assert avg_gen[12] > avg_gen[18]  # Noon > 6 PM
    
    # All values should be non-negative
    assert all(val >= 0 for val in avg_gen)
    assert all(val >= 0 for val in current_gen)


@pytest.mark.parametrize(
    "interpolate_flag",
    [True, False],
)
def test_interpolation_behavior(mock_data_provider, interpolate_flag):
    """Test model behavior with and without interpolation."""
    test_data = pd.DataFrame({
        'pv_generation': [50.0, None, 100.0, None, 25.0]
    }, index=pd.date_range('2024-01-01', periods=5, freq='h'))
    
    mock_data_provider.get_data.return_value = test_data
    
    model = HistoricalAveragePVGenerationModel(
        data_provider=mock_data_provider,
        interpolate=interpolate_flag
    )
    
    assert model.interpolate == interpolate_flag


def test_edge_case_dates(pv_model, sample_pv_data):
    """Test model with edge case dates."""
    edge_dates = [
        datetime.date(2024, 2, 29),  # Leap year
        datetime.date(2024, 12, 31), # Year end
        datetime.date(2024, 1, 1),   # Year start
        datetime.date(2000, 1, 1),   # Different year
    ]
    
    pv_model.data_provider.get_data.return_value = sample_pv_data
    
    for test_date in edge_dates:
        with patch.object(pv_model.helper, 'get_current_date') as mock_current_date, \
             patch.object(pv_model.helper, 'get_prior_date') as mock_prior_date, \
             patch.object(pv_model.helper, 'get_prior_data') as mock_prior_data, \
             patch.object(pv_model.helper, 'get_current_date_data') as mock_current_data, \
             patch.object(pv_model.helper, 'get_generation_current_date') as mock_current_gen, \
             patch.object(pv_model, 'get_average_generations_last_week') as mock_avg:
            
            # Setup return values to avoid timezone comparisons
            mock_current_date.return_value = datetime.datetime(test_date.year, test_date.month, test_date.day, 0, 0, tzinfo=pytz.utc)
            # Calculate prior date properly using timedelta
            prior_date_dt = datetime.datetime(test_date.year, test_date.month, test_date.day, 0, 0, tzinfo=pytz.utc) - datetime.timedelta(days=7)
            mock_prior_date.return_value = prior_date_dt
            mock_prior_data.return_value = sample_pv_data
            mock_current_data.return_value = pd.DataFrame({'pv_generation': [25] * 24})
            mock_avg.return_value = [15.0] * 24
            mock_current_gen.return_value = [25.0] * 24
            
            avg_gen, current_gen = pv_model.get_generation(test_date)
            
            assert len(avg_gen) == 24
            assert len(current_gen) == 24
            assert all(val >= 0 for val in avg_gen)
            assert all(val >= 0 for val in current_gen)


def test_get_generations_backward_compatibility(pv_model, test_date, sample_pv_data):
    """Test that get_generations method still works for backward compatibility."""
    pv_model.data_provider.get_data.return_value = sample_pv_data
    
    with patch.object(pv_model.helper, 'get_current_date') as mock_current_date, \
         patch.object(pv_model.helper, 'get_prior_date') as mock_prior_date, \
         patch.object(pv_model.helper, 'get_prior_data') as mock_prior_data, \
         patch.object(pv_model.helper, 'get_current_date_data') as mock_current_data, \
         patch.object(pv_model.helper, 'get_generation_current_date') as mock_current_gen, \
         patch.object(pv_model, 'get_average_generations_last_week') as mock_avg:
        
        # Setup return values to avoid timezone comparisons
        mock_current_date.return_value = datetime.datetime(2024, 6, 15, 0, 0, tzinfo=pytz.utc)
        mock_prior_date.return_value = datetime.datetime(2024, 6, 8, 0, 0, tzinfo=pytz.utc)
        mock_prior_data.return_value = sample_pv_data
        mock_current_data.return_value = pd.DataFrame({'pv_generation': [20] * 24})
        mock_avg.return_value = [10.0] * 24
        mock_current_gen.return_value = [20.0] * 24
        
        avg_gen, current_gen = pv_model.get_generations(test_date)
        
        assert isinstance(avg_gen, list)
        assert isinstance(current_gen, list)
        assert len(avg_gen) == 24
        assert len(current_gen) == 24


if __name__ == "__main__":
    pytest.main([__file__])
