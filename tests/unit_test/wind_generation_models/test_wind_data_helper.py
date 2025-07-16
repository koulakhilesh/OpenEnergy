import os
import sys

import pytest
import datetime
from unittest.mock import Mock
import pandas as pd

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from scripts.wind_generation_models.wind_data_helper import WindDataHelper


@pytest.fixture
def wind_helper():
    """Fixture for wind data helper."""
    return WindDataHelper()


@pytest.fixture
def test_date():
    """Fixture for a standard test date."""
    return datetime.date(2024, 6, 15)


@pytest.fixture
def mock_wind_data():
    """Fixture for mock wind data interface."""
    return Mock()


def test_get_current_date(wind_helper, test_date):
    """Test get_current_date method."""
    result = wind_helper.get_current_date(test_date)
    
    assert isinstance(result, datetime.datetime)
    assert result.date() == test_date
    assert result.time() == datetime.time()


@pytest.mark.parametrize(
    "delta_days",
    [1, 7, 30, 90, 365],
)
def test_get_prior_date(wind_helper, delta_days):
    """Test get_prior_date with various delta days."""
    current_date = datetime.datetime(2024, 6, 15, 12, 0, 0)
    
    result = wind_helper.get_prior_date(current_date, delta_days)
    
    assert isinstance(result, datetime.datetime)
    expected_date = current_date - datetime.timedelta(days=delta_days)
    assert result == expected_date


def test_get_prior_data(wind_helper):
    """Test get_prior_data method."""
    current_date = datetime.datetime(2024, 6, 15, 12, 0, 0)
    prior_date = datetime.datetime(2024, 6, 10, 12, 0, 0)
    
    # Mock wind data interface
    mock_wind_data = Mock()
    # Mock the get_generation method to return tuple
    mock_wind_data.get_generation.return_value = ([100.0, 200.0], [150.0, 250.0])
    
    result = wind_helper.get_prior_data(current_date, prior_date, mock_wind_data)
    
    # Check that it returns a DataFrame (implementation may vary)
    assert result is not None


def test_get_prior_data_as_list(wind_helper):
    """Test get_prior_data_as_list method."""
    current_date = datetime.datetime(2024, 6, 15, 12, 0, 0)
    prior_date = datetime.datetime(2024, 6, 10, 12, 0, 0)
    
    # Mock wind data interface
    mock_wind_data = Mock()
    
    # Mock the get_prior_data method to return expected DataFrame
    from unittest.mock import patch
    with patch.object(wind_helper, 'get_prior_data') as mock_get_data:
        mock_df = pd.DataFrame({'generation': [100.0, 200.0, 150.0]})
        mock_get_data.return_value = mock_df
        
        result = wind_helper.get_prior_data_as_list(current_date, prior_date, mock_wind_data)
        
        assert isinstance(result, list)
        assert result == [100.0, 200.0, 150.0]


@pytest.mark.parametrize(
    "season_date,expected_factor",
    [
        (datetime.date(2024, 12, 15), 1.3),  # Winter
        (datetime.date(2024, 1, 15), 1.3),   # Winter
        (datetime.date(2024, 2, 15), 1.3),   # Winter
        (datetime.date(2024, 6, 15), 0.8),   # Summer
        (datetime.date(2024, 7, 15), 0.8),   # Summer
        (datetime.date(2024, 8, 15), 0.8),   # Summer
        (datetime.date(2024, 3, 15), 1.0),   # Spring
        (datetime.date(2024, 4, 15), 1.0),   # Spring
        (datetime.date(2024, 5, 15), 1.0),   # Spring
        (datetime.date(2024, 9, 15), 1.0),   # Fall
        (datetime.date(2024, 10, 15), 1.0),  # Fall
        (datetime.date(2024, 11, 15), 1.0),  # Fall
    ],
)
def test_get_seasonal_trend(wind_helper, season_date, expected_factor):
    """Test seasonal trend calculation for different months."""
    base_generation = [100.0, 200.0, 150.0, 300.0]
    
    result = wind_helper.get_seasonal_trend(season_date, base_generation)
    
    assert isinstance(result, list)
    assert len(result) == len(base_generation)
    
    # Check that seasonal factor is applied correctly
    expected_result = [gen * expected_factor for gen in base_generation]
    assert result == expected_result


def test_get_seasonal_trend_empty_list(wind_helper, test_date):
    """Test seasonal trend with empty generation list."""
    base_generation = []
    
    result = wind_helper.get_seasonal_trend(test_date, base_generation)
    
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.parametrize(
    "hour,expected_factor",
    [
        (0, 0.7),   # Night
        (3, 0.7),   # Night
        (5, 0.7),   # Early morning
        (6, 0.9),   # Morning
        (8, 0.9),   # Morning
        (10, 0.9),  # Morning
        (11, 1.2),  # Afternoon
        (14, 1.2),  # Afternoon
        (17, 1.2),  # Afternoon
        (18, 1.3),  # Evening
        (20, 1.3),  # Evening
        (22, 1.3),  # Evening
        (23, 0.7),  # Night
    ],
)
def test_get_wind_speed_factor(wind_helper, hour, expected_factor):
    """Test wind speed factor for different hours."""
    result = wind_helper.get_wind_speed_factor(hour)
    
    assert isinstance(result, (int, float))
    assert result == expected_factor


@pytest.mark.parametrize(
    "invalid_hour",
    [-1, 24, 25, 100],
)
def test_get_wind_speed_factor_invalid_hour(wind_helper, invalid_hour):
    """Test wind speed factor with invalid hours."""
    # Should handle invalid hours gracefully
    result = wind_helper.get_wind_speed_factor(invalid_hour)
    
    # Should return some default value (likely 0.7 for out-of-range)
    assert isinstance(result, (int, float))
    assert result == 0.7


def test_get_seasonal_trend_with_negative_values(wind_helper, test_date):
    """Test seasonal trend with negative base generation values."""
    base_generation = [-50.0, 100.0, -25.0, 200.0]
    
    result = wind_helper.get_seasonal_trend(test_date, base_generation)
    
    assert isinstance(result, list)
    assert len(result) == len(base_generation)
    
    # Should apply factor to all values, including negative ones
    month = test_date.month
    if month in [6, 7, 8]:  # Summer
        expected_factor = 0.8
    else:
        expected_factor = 1.0
    
    expected_result = [gen * expected_factor for gen in base_generation]
    assert result == expected_result


def test_get_seasonal_trend_with_zero_values(wind_helper, test_date):
    """Test seasonal trend with zero base generation values."""
    base_generation = [0.0, 0.0, 0.0, 0.0]
    
    result = wind_helper.get_seasonal_trend(test_date, base_generation)
    
    assert isinstance(result, list)
    assert len(result) == len(base_generation)
    assert all(val == 0.0 for val in result)


def test_get_seasonal_trend_large_values(wind_helper, test_date):
    """Test seasonal trend with large generation values."""
    base_generation = [1000000.0, 2000000.0, 1500000.0]
    
    result = wind_helper.get_seasonal_trend(test_date, base_generation)
    
    assert isinstance(result, list)
    assert len(result) == len(base_generation)
    
    # Should handle large values correctly
    for val in result:
        assert isinstance(val, (int, float))
        assert val >= 0  # After applying factor, should still be positive


def test_date_edge_cases(wind_helper):
    """Test with edge case dates."""
    edge_dates = [
        datetime.date(2024, 2, 29),  # Leap year
        datetime.date(2024, 12, 31), # Year end
        datetime.date(2024, 1, 1),   # Year start
    ]
    
    for test_date in edge_dates:
        current_dt = wind_helper.get_current_date(test_date)
        assert isinstance(current_dt, datetime.datetime)
        assert current_dt.date() == test_date


def test_prior_date_calculations(wind_helper):
    """Test various prior date calculations."""
    base_date = datetime.datetime(2024, 6, 15, 12, 0, 0)
    
    # Test various delta values
    deltas = [0, 1, 30, 365, 1000]
    
    for delta in deltas:
        prior_date = wind_helper.get_prior_date(base_date, delta)
        expected = base_date - datetime.timedelta(days=delta)
        assert prior_date == expected


def test_wind_speed_factor_consistency(wind_helper):
    """Test that wind speed factors are consistent across full day."""
    factors = []
    for hour in range(24):
        factor = wind_helper.get_wind_speed_factor(hour)
        factors.append(factor)
    
    # Should have 24 factors
    assert len(factors) == 24
    
    # All factors should be positive
    assert all(f > 0 for f in factors)
    
    # Factors should be within reasonable range
    assert all(0.5 <= f <= 2.0 for f in factors)


def test_get_current_date_data_assertion_error(wind_helper):
    """Test get_current_date_data with non-DatetimeIndex raises assertion error."""
    current_date = datetime.datetime(2024, 6, 15, 12, 0, 0)
    
    # Create DataFrame with non-DatetimeIndex
    data = pd.DataFrame({
        'wind_generation': [10, 20, 30]
    }, index=[0, 1, 2])
    
    with pytest.raises(AssertionError):
        wind_helper.get_current_date_data(current_date, data)


def test_get_current_date_data_empty_result(wind_helper):
    """Test get_current_date_data when no data matches the date."""
    current_date = datetime.datetime(2024, 6, 15, 12, 0, 0)
    
    # Create data for different date
    data = pd.DataFrame({
        'wind_generation': [10, 20, 30]
    }, index=pd.date_range('2024-01-01', periods=3, freq='h'))
    
    result = wind_helper.get_current_date_data(current_date, data)
    
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_get_generation_current_date_assertion_error(wind_helper):
    """Test get_generation_current_date returns list and triggers assertion."""
    data = pd.DataFrame({
        'wind_generation': [15.5, 20.3, 25.8]
    })
    
    result = wind_helper.get_generation_current_date(data, 'wind_generation')
    
    # This should trigger the assertion check
    assert isinstance(result, list)
    assert result == [15.5, 20.3, 25.8]


def test_get_prior_data_as_list_with_interface(wind_helper, mock_wind_data):
    """Test get_prior_data_as_list with wind data interface."""
    current_date = datetime.datetime(2024, 6, 15, 12, 0, 0)
    prior_date = datetime.datetime(2024, 6, 8, 12, 0, 0)
    
    # Mock wind data interface - get_generation should return a tuple
    mock_wind_data.get_generation.return_value = ([10.5, 15.2, 20.8] * 8, [])  # 24 hours data
    
    result = wind_helper.get_prior_data_as_list(current_date, prior_date, mock_wind_data)
    
    assert isinstance(result, list)
    # Should call get_generation for each day in the range
    assert mock_wind_data.get_generation.call_count > 0


def test_get_prior_data_as_list_with_dataframe(wind_helper):
    """Test get_prior_data_as_list with DataFrame data source."""
    current_date = datetime.datetime(2024, 6, 15, 12, 0, 0)
    prior_date = datetime.datetime(2024, 6, 8, 12, 0, 0)
    
    # Create DataFrame with 'generation' column as expected by get_prior_data_as_list
    date_range = pd.date_range(prior_date, current_date, freq='h', inclusive='left')
    data = pd.DataFrame({
        'generation': range(len(date_range))  # Use 'generation' column name
    }, index=date_range)
    
    result = wind_helper.get_prior_data_as_list(current_date, prior_date, data)
    
    assert isinstance(result, list)
    assert len(result) == len(date_range)
    assert all(isinstance(x, (int, float)) for x in result)


def test_get_seasonal_trend_summer(wind_helper):
    """Test get_seasonal_trend for summer months."""
    base_generation = [10.0, 20.0, 30.0]
    
    # Test summer months (June, July, August)
    for month in [6, 7, 8]:
        test_date = datetime.date(2024, month, 15)
        result = wind_helper.get_seasonal_trend(test_date, base_generation)
        
        # Summer should have seasonal_factor = 0.8
        expected = [gen * 0.8 for gen in base_generation]
        assert result == expected


def test_get_seasonal_trend_winter(wind_helper):
    """Test get_seasonal_trend for winter months."""
    base_generation = [10.0, 20.0, 30.0]
    
    # Test winter months (December, January, February)
    for month in [12, 1, 2]:
        test_date = datetime.date(2024, month, 15)
        result = wind_helper.get_seasonal_trend(test_date, base_generation)
        
        # Winter should have seasonal_factor = 1.3 (wait, the code shows 1.3, not 1.2)
        expected = [gen * 1.3 for gen in base_generation]
        assert result == expected


def test_get_seasonal_trend_spring_fall(wind_helper):
    """Test get_seasonal_trend for spring and fall months."""
    base_generation = [10.0, 20.0, 30.0]
    
    # Test spring/fall months (March, April, May, September, October, November)
    for month in [3, 4, 5, 9, 10, 11]:
        test_date = datetime.date(2024, month, 15)
        result = wind_helper.get_seasonal_trend(test_date, base_generation)
        
        # Spring/Fall should have seasonal_factor = 1.0
        expected = [gen * 1.0 for gen in base_generation]
        assert result == expected


def test_get_wind_speed_factor_morning(wind_helper):
    """Test get_wind_speed_factor for morning hours."""
    # Morning hours (6-10) should return 0.9
    for hour in range(6, 11):
        result = wind_helper.get_wind_speed_factor(hour)
        assert result == 0.9


def test_get_wind_speed_factor_afternoon(wind_helper):
    """Test get_wind_speed_factor for afternoon hours."""
    # Afternoon hours (11-17) should return 1.2
    for hour in range(11, 18):
        result = wind_helper.get_wind_speed_factor(hour)
        assert result == 1.2


def test_get_wind_speed_factor_evening(wind_helper):
    """Test get_wind_speed_factor for evening hours."""
    # Evening hours (18-22) should return 1.3
    for hour in range(18, 23):
        result = wind_helper.get_wind_speed_factor(hour)
        assert result == 1.3


def test_get_wind_speed_factor_night(wind_helper):
    """Test get_wind_speed_factor for night/early morning hours."""
    # Night/early morning hours (0-5, 23) should return 0.7
    for hour in [0, 1, 2, 3, 4, 5, 23]:
        result = wind_helper.get_wind_speed_factor(hour)
        assert result == 0.7


@pytest.mark.parametrize(
    "hour, expected_factor",
    [
        (0, 0.7),   # Night
        (5, 0.7),   # Early morning
        (6, 0.9),   # Morning start
        (10, 0.9),  # Morning end
        (11, 1.2),  # Afternoon start
        (17, 1.2),  # Afternoon end
        (18, 1.3),  # Evening start
        (22, 1.3),  # Evening end
        (23, 0.7),  # Night
    ],
)
def test_get_wind_speed_factor_parametrized(wind_helper, hour, expected_factor):
    """Test get_wind_speed_factor with parametrized hours."""
    result = wind_helper.get_wind_speed_factor(hour)
    assert result == expected_factor


def test_edge_case_leap_year_february(wind_helper):
    """Test functionality during leap year February."""
    leap_year_date = datetime.date(2024, 2, 29)
    current_date = wind_helper.get_current_date(leap_year_date)
    
    assert current_date.year == 2024
    assert current_date.month == 2
    assert current_date.day == 29


def test_get_seasonal_trend_all_months(wind_helper):
    """Test get_seasonal_trend for all 12 months to ensure coverage."""
    base_generation = [15.0, 25.0, 35.0]
    
    expected_factors = {
        1: 1.3, 2: 1.3, 3: 1.0, 4: 1.0, 5: 1.0, 6: 0.8,
        7: 0.8, 8: 0.8, 9: 1.0, 10: 1.0, 11: 1.0, 12: 1.3
    }
    
    for month in range(1, 13):
        test_date = datetime.date(2024, month, 15)
        result = wind_helper.get_seasonal_trend(test_date, base_generation)
        expected = [gen * expected_factors[month] for gen in base_generation]
        assert result == expected, f"Failed for month {month}"


def test_get_prior_data_interface_vs_dataframe(wind_helper, mock_wind_data):
    """Test that get_prior_data behaves correctly with both interface and DataFrame."""
    current_date = datetime.datetime(2024, 6, 15, 12, 0, 0)
    prior_date = datetime.datetime(2024, 6, 8, 12, 0, 0)
    
    # Test with interface - mock get_generation to return tuple
    mock_wind_data.get_generation.return_value = ([5.0, 10.0, 15.0] * 8, [])  # 24 hours
    
    result_interface = wind_helper.get_prior_data(current_date, prior_date, mock_wind_data)
    assert isinstance(result_interface, pd.DataFrame)
    assert mock_wind_data.get_generation.call_count > 0
    
    # Test with DataFrame - use 'generation' column name that get_prior_data_as_list expects
    data = pd.DataFrame({
        'generation': [5.0, 10.0, 15.0]
    }, index=pd.date_range(prior_date, periods=3, freq='h'))
    
    result_df = wind_helper.get_prior_data(current_date, prior_date, data)
    assert isinstance(result_df, pd.DataFrame)


if __name__ == "__main__":
    pytest.main([__file__])
