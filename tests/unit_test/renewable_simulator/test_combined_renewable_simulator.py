import os
import sys
import datetime
from unittest.mock import Mock, patch, MagicMock
import pytest
import pandas as pd

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from scripts.renewable_simulator.combined_renewable_simulator import (
    CombinedRenewableSimulator,
    RenewableAsset,
)
from scripts.renewable_simulator.interfaces import IRenewablePortfolio
from scripts.assets import Battery, PVSystem, WindSystem
from scripts.pv_generation_models.interfaces import IPVData
from scripts.wind_generation_models.interfaces import IWindData


@pytest.fixture
def simulator():
    """Fixture for combined renewable simulator."""
    return CombinedRenewableSimulator()


@pytest.fixture
def mock_pv_system():
    """Fixture for mock PV system."""
    return Mock(spec=PVSystem)


@pytest.fixture
def mock_wind_system():
    """Fixture for mock wind system."""
    return Mock(spec=WindSystem)


@pytest.fixture
def mock_battery():
    """Fixture for mock battery."""
    battery = Mock(spec=Battery)
    battery.capacity_mwh = 10.0
    return battery


@pytest.fixture
def mock_pv_data():
    """Fixture for mock PV data provider."""
    mock_data = Mock(spec=IPVData)
    mock_data.get_generation.return_value = ([50.0] * 24, [100.0] * 24)
    return mock_data


@pytest.fixture
def mock_wind_data():
    """Fixture for mock wind data provider."""
    mock_data = Mock(spec=IWindData)
    mock_data.get_generation.return_value = ([30.0] * 24, [80.0] * 24)
    return mock_data


@pytest.fixture
def test_date():
    """Fixture for a standard test date."""
    return datetime.date(2024, 6, 15)


@pytest.fixture
def sample_prices():
    """Fixture for sample electricity prices."""
    return [50.0, 40.0, 35.0, 30.0, 30.0, 35.0, 45.0, 60.0, 
            70.0, 75.0, 80.0, 85.0, 90.0, 85.0, 80.0, 75.0,
            70.0, 65.0, 60.0, 55.0, 50.0, 45.0, 40.0, 35.0]


# Tests for RenewableAsset dataclass
class TestRenewableAsset:
    
    def test_renewable_asset_creation(self, mock_pv_system, mock_pv_data):
        """Test creation of RenewableAsset dataclass."""
        asset = RenewableAsset(
            name="solar_farm_1",
            asset_type="solar",
            capacity_mw=100.0,
            system=mock_pv_system,
            data_provider=mock_pv_data,
        )
        
        assert asset.name == "solar_farm_1"
        assert asset.asset_type == "solar"
        assert asset.capacity_mw == 100.0
        assert asset.system == mock_pv_system
        assert asset.data_provider == mock_pv_data

    def test_renewable_asset_battery(self, mock_battery):
        """Test creation of battery RenewableAsset."""
        asset = RenewableAsset(
            name="battery_storage",
            asset_type="battery",
            capacity_mw=10.0,
            system=mock_battery,
            data_provider=None,
        )
        
        assert asset.name == "battery_storage"
        assert asset.asset_type == "battery"
        assert asset.capacity_mw == 10.0
        assert asset.system == mock_battery
        assert asset.data_provider is None


# Tests for CombinedRenewableSimulator
class TestCombinedRenewableSimulator:
    
    def test_initialization(self):
        """Test simulator initialization."""
        simulator = CombinedRenewableSimulator()
        
        assert isinstance(simulator.assets, list)
        assert len(simulator.assets) == 0
        assert simulator.battery is None

    def test_interface_compliance(self, simulator):
        """Test that simulator implements IRenewablePortfolio interface."""
        assert isinstance(simulator, IRenewablePortfolio)
        assert hasattr(simulator, 'calculate_total_generation')
        assert hasattr(simulator, 'get_asset_breakdown')
        assert callable(simulator.calculate_total_generation)
        assert callable(simulator.get_asset_breakdown)

    def test_add_solar_asset(self, simulator, mock_pv_system, mock_pv_data):
        """Test adding a solar asset to the portfolio."""
        simulator.add_solar_asset(
            name="solar_farm_1",
            capacity_mw=100.0,
            pv_system=mock_pv_system,
            pv_data=mock_pv_data,
        )
        
        assert len(simulator.assets) == 1
        asset = simulator.assets[0]
        assert asset.name == "solar_farm_1"
        assert asset.asset_type == "solar"
        assert asset.capacity_mw == 100.0
        assert asset.system == mock_pv_system
        assert asset.data_provider == mock_pv_data

    def test_add_wind_asset(self, simulator, mock_wind_system, mock_wind_data):
        """Test adding a wind asset to the portfolio."""
        simulator.add_wind_asset(
            name="wind_farm_1",
            capacity_mw=150.0,
            wind_system=mock_wind_system,
            wind_data=mock_wind_data,
        )
        
        assert len(simulator.assets) == 1
        asset = simulator.assets[0]
        assert asset.name == "wind_farm_1"
        assert asset.asset_type == "wind"
        assert asset.capacity_mw == 150.0
        assert asset.system == mock_wind_system
        assert asset.data_provider == mock_wind_data

    def test_add_battery_storage(self, simulator, mock_battery):
        """Test adding battery storage to the portfolio."""
        simulator.add_battery_storage(mock_battery)
        
        assert simulator.battery == mock_battery
        assert len(simulator.assets) == 1
        
        asset = simulator.assets[0]
        assert asset.name == "battery_storage"
        assert asset.asset_type == "battery"
        assert asset.capacity_mw == mock_battery.capacity_mwh
        assert asset.system == mock_battery
        assert asset.data_provider is None

    def test_calculate_total_generation_empty_portfolio(self, simulator, test_date):
        """Test total generation calculation with empty portfolio."""
        total_actual, total_potential = simulator.calculate_total_generation(test_date)
        
        assert isinstance(total_actual, list)
        assert isinstance(total_potential, list)
        assert len(total_actual) == 24
        assert len(total_potential) == 24
        assert all(val == 0.0 for val in total_actual)
        assert all(val == 0.0 for val in total_potential)

    def test_calculate_total_generation_with_assets(
        self, simulator, mock_pv_system, mock_pv_data, 
        mock_wind_system, mock_wind_data, test_date
    ):
        """Test total generation calculation with multiple assets."""
        # Add solar asset
        simulator.add_solar_asset("solar_1", 100.0, mock_pv_system, mock_pv_data)
        
        # Add wind asset
        simulator.add_wind_asset("wind_1", 150.0, mock_wind_system, mock_wind_data)
        
        total_actual, total_potential = simulator.calculate_total_generation(test_date)
        
        assert len(total_actual) == 24
        assert len(total_potential) == 24
        
        # Should be sum of solar (50) + wind (30) = 80 for actual
        # Should be sum of solar (100) + wind (80) = 180 for potential
        assert all(val == 80.0 for val in total_actual)
        assert all(val == 180.0 for val in total_potential)
        
        # Verify that get_generation was called for both assets
        mock_pv_data.get_generation.assert_called_once_with(test_date)
        mock_wind_data.get_generation.assert_called_once_with(test_date)

    def test_calculate_total_generation_with_battery_only(
        self, simulator, mock_battery, test_date
    ):
        """Test total generation calculation with battery only (should be zero)."""
        simulator.add_battery_storage(mock_battery)
        
        total_actual, total_potential = simulator.calculate_total_generation(test_date)
        
        assert len(total_actual) == 24
        assert len(total_potential) == 24
        assert all(val == 0.0 for val in total_actual)
        assert all(val == 0.0 for val in total_potential)

    def test_calculate_total_generation_mismatched_data_length(
        self, simulator, mock_pv_system, test_date
    ):
        """Test total generation with mismatched data lengths."""
        mock_pv_data = Mock(spec=IPVData)
        # Return shorter lists
        mock_pv_data.get_generation.return_value = ([50.0] * 12, [100.0] * 12)
        
        simulator.add_solar_asset("solar_1", 100.0, mock_pv_system, mock_pv_data)
        
        total_actual, total_potential = simulator.calculate_total_generation(test_date)
        
        assert len(total_actual) == 24
        assert len(total_potential) == 24
        
        # First 12 hours should have values, last 12 should be 0
        for hour in range(12):
            assert total_actual[hour] == 50.0
            assert total_potential[hour] == 100.0
        
        for hour in range(12, 24):
            assert total_actual[hour] == 0.0
            assert total_potential[hour] == 0.0

    def test_get_asset_breakdown_empty_portfolio(self, simulator, test_date):
        """Test asset breakdown with empty portfolio."""
        breakdown = simulator.get_asset_breakdown(test_date)
        
        assert isinstance(breakdown, dict)
        assert len(breakdown) == 0

    def test_get_asset_breakdown_with_assets(
        self, simulator, mock_pv_system, mock_pv_data,
        mock_wind_system, mock_wind_data, test_date
    ):
        """Test asset breakdown with multiple assets."""
        # Add solar asset
        simulator.add_solar_asset("solar_1", 100.0, mock_pv_system, mock_pv_data)
        
        # Add wind asset  
        simulator.add_wind_asset("wind_1", 150.0, mock_wind_system, mock_wind_data)
        
        breakdown = simulator.get_asset_breakdown(test_date)
        
        assert isinstance(breakdown, dict)
        assert "solar" in breakdown
        assert "wind" in breakdown
        
        solar_actual, solar_potential = breakdown["solar"]
        wind_actual, wind_potential = breakdown["wind"]
        
        assert len(solar_actual) == 24
        assert len(solar_potential) == 24
        assert len(wind_actual) == 24
        assert len(wind_potential) == 24
        
        assert all(val == 50.0 for val in solar_actual)
        assert all(val == 100.0 for val in solar_potential)
        assert all(val == 30.0 for val in wind_actual)
        assert all(val == 80.0 for val in wind_potential)

    def test_get_asset_breakdown_multiple_same_type(
        self, simulator, mock_pv_system, test_date
    ):
        """Test asset breakdown with multiple assets of same type."""
        mock_pv_data_1 = Mock(spec=IPVData)
        mock_pv_data_1.get_generation.return_value = ([40.0] * 24, [80.0] * 24)
        
        mock_pv_data_2 = Mock(spec=IPVData)
        mock_pv_data_2.get_generation.return_value = ([60.0] * 24, [120.0] * 24)
        
        # Add two solar assets
        simulator.add_solar_asset("solar_1", 100.0, mock_pv_system, mock_pv_data_1)
        simulator.add_solar_asset("solar_2", 150.0, mock_pv_system, mock_pv_data_2)
        
        breakdown = simulator.get_asset_breakdown(test_date)
        
        assert "solar" in breakdown
        solar_actual, solar_potential = breakdown["solar"]
        
        # Should aggregate both solar assets: 40 + 60 = 100, 80 + 120 = 200
        assert all(val == 100.0 for val in solar_actual)
        assert all(val == 200.0 for val in solar_potential)

    def test_optimize_dispatch(
        self, simulator, mock_pv_system, mock_pv_data, test_date, sample_prices
    ):
        """Test dispatch optimization."""
        simulator.add_solar_asset("solar_1", 100.0, mock_pv_system, mock_pv_data)
        
        dispatch_df = simulator.optimize_dispatch(test_date, sample_prices)
        
        assert isinstance(dispatch_df, pd.DataFrame)
        assert len(dispatch_df) == 24
        
        expected_columns = [
            "hour", "renewable_generation_mw", "battery_charge_mw",
            "battery_discharge_mw", "net_export_mw", "revenue", "price"
        ]
        
        for col in expected_columns:
            assert col in dispatch_df.columns
        
        # Check that renewable generation matches expected values
        assert all(dispatch_df["renewable_generation_mw"] == 50.0)
        assert all(dispatch_df["net_export_mw"] == 50.0)
        
        # Check revenue calculation
        for hour in range(24):
            expected_revenue = 50.0 * sample_prices[hour]
            assert dispatch_df.loc[hour, "revenue"] == expected_revenue

    def test_optimize_dispatch_empty_portfolio(self, simulator, test_date, sample_prices):
        """Test dispatch optimization with empty portfolio."""
        dispatch_df = simulator.optimize_dispatch(test_date, sample_prices)
        
        assert isinstance(dispatch_df, pd.DataFrame)
        assert len(dispatch_df) == 24
        assert all(dispatch_df["renewable_generation_mw"] == 0.0)
        assert all(dispatch_df["net_export_mw"] == 0.0)
        assert all(dispatch_df["revenue"] == 0.0)

    def test_optimize_dispatch_mismatched_prices(
        self, simulator, mock_pv_system, mock_pv_data, test_date
    ):
        """Test dispatch optimization with mismatched price length."""
        simulator.add_solar_asset("solar_1", 100.0, mock_pv_system, mock_pv_data)
        
        # Provide only 12 hours of prices
        short_prices = [50.0] * 12
        
        dispatch_df = simulator.optimize_dispatch(test_date, short_prices)
        
        assert len(dispatch_df) == 24
        
        # First 12 hours should use provided prices
        for hour in range(12):
            assert dispatch_df.loc[hour, "price"] == 50.0
        
        # Last 12 hours should use the last price
        for hour in range(12, 24):
            assert dispatch_df.loc[hour, "price"] == 50.0

    def test_calculate_portfolio_metrics(
        self, simulator, mock_pv_system, mock_pv_data, test_date, sample_prices
    ):
        """Test portfolio metrics calculation."""
        simulator.add_solar_asset("solar_1", 100.0, mock_pv_system, mock_pv_data)
        
        metrics = simulator.calculate_portfolio_metrics(test_date, sample_prices)
        
        assert isinstance(metrics, dict)
        
        expected_keys = [
            "total_generation_mwh", "total_potential_mwh", "capacity_factor",
            "total_revenue", "average_price_per_mwh", "revenue_per_mwh"
        ]
        
        for key in expected_keys:
            assert key in metrics
        
        # Check calculated values
        assert metrics["total_generation_mwh"] == 50.0 * 24  # 1200 MWh
        assert metrics["total_potential_mwh"] == 100.0 * 24  # 2400 MWh
        assert metrics["capacity_factor"] == 0.5  # 50% capacity factor
        
        expected_total_revenue = sum(50.0 * price for price in sample_prices)
        assert metrics["total_revenue"] == expected_total_revenue
        
        expected_avg_price = sum(sample_prices) / len(sample_prices)
        assert metrics["average_price_per_mwh"] == expected_avg_price

    def test_calculate_portfolio_metrics_zero_generation(
        self, simulator, test_date, sample_prices
    ):
        """Test portfolio metrics with zero generation."""
        metrics = simulator.calculate_portfolio_metrics(test_date, sample_prices)
        
        assert metrics["total_generation_mwh"] == 0
        assert metrics["total_potential_mwh"] == 0
        assert metrics["capacity_factor"] == 0
        assert metrics["total_revenue"] == 0
        assert metrics["revenue_per_mwh"] == 0

    def test_get_portfolio_summary_empty(self, simulator):
        """Test portfolio summary with empty portfolio."""
        summary = simulator.get_portfolio_summary()
        
        assert isinstance(summary, dict)
        assert summary["total_assets"] == 0
        assert summary["asset_types"] == {}
        assert summary["total_capacity_mw"] == 0.0
        assert summary["has_battery"] is False

    def test_get_portfolio_summary_with_assets(
        self, simulator, mock_pv_system, mock_pv_data,
        mock_wind_system, mock_wind_data, mock_battery
    ):
        """Test portfolio summary with multiple assets."""
        # Add various assets
        simulator.add_solar_asset("solar_1", 100.0, mock_pv_system, mock_pv_data)
        simulator.add_solar_asset("solar_2", 150.0, mock_pv_system, mock_pv_data)
        simulator.add_wind_asset("wind_1", 200.0, mock_wind_system, mock_wind_data)
        simulator.add_battery_storage(mock_battery)
        
        summary = simulator.get_portfolio_summary()
        
        assert summary["total_assets"] == 4
        assert summary["has_battery"] is True
        assert summary["total_capacity_mw"] == 460.0  # 100 + 150 + 200 + 10
        
        asset_types = summary["asset_types"]
        assert "solar" in asset_types
        assert "wind" in asset_types
        assert "battery" in asset_types
        
        assert asset_types["solar"]["count"] == 2
        assert asset_types["solar"]["total_capacity_mw"] == 250.0
        
        assert asset_types["wind"]["count"] == 1
        assert asset_types["wind"]["total_capacity_mw"] == 200.0
        
        assert asset_types["battery"]["count"] == 1
        assert asset_types["battery"]["total_capacity_mw"] == 10.0

    @pytest.mark.parametrize(
        "test_date",
        [
            datetime.date(2024, 1, 1),   # New Year
            datetime.date(2024, 6, 21),  # Summer solstice
            datetime.date(2024, 12, 21), # Winter solstice
            datetime.date(2024, 2, 29),  # Leap year
        ],
    )
    def test_calculate_total_generation_various_dates(
        self, simulator, mock_pv_system, mock_pv_data, test_date
    ):
        """Test total generation calculation with various dates."""
        simulator.add_solar_asset("solar_1", 100.0, mock_pv_system, mock_pv_data)
        
        total_actual, total_potential = simulator.calculate_total_generation(test_date)
        
        assert len(total_actual) == 24
        assert len(total_potential) == 24
        assert all(isinstance(val, float) for val in total_actual)
        assert all(isinstance(val, float) for val in total_potential)
        
        # Verify get_generation was called with the correct date
        mock_pv_data.get_generation.assert_called_with(test_date)

    def test_edge_cases_empty_lists(self, simulator, mock_pv_system, test_date):
        """Test edge cases with empty generation lists."""
        mock_pv_data = Mock(spec=IPVData)
        mock_pv_data.get_generation.return_value = ([], [])
        
        simulator.add_solar_asset("solar_1", 100.0, mock_pv_system, mock_pv_data)
        
        total_actual, total_potential = simulator.calculate_total_generation(test_date)
        
        assert len(total_actual) == 24
        assert len(total_potential) == 24
        assert all(val == 0.0 for val in total_actual)
        assert all(val == 0.0 for val in total_potential)

    def test_integration_with_real_workflow(
        self, simulator, mock_pv_system, mock_pv_data,
        mock_wind_system, mock_wind_data, mock_battery,
        test_date, sample_prices
    ):
        """Test full integration workflow."""
        # Build a complete portfolio
        simulator.add_solar_asset("solar_farm", 200.0, mock_pv_system, mock_pv_data)
        simulator.add_wind_asset("wind_farm", 300.0, mock_wind_system, mock_wind_data)
        simulator.add_battery_storage(mock_battery)
        
        # Test the complete workflow
        total_actual, total_potential = simulator.calculate_total_generation(test_date)
        breakdown = simulator.get_asset_breakdown(test_date)
        dispatch = simulator.optimize_dispatch(test_date, sample_prices)
        metrics = simulator.calculate_portfolio_metrics(test_date, sample_prices)
        summary = simulator.get_portfolio_summary()
        
        # Verify all components work together
        assert len(total_actual) == 24
        assert len(breakdown) == 2  # solar and wind
        assert len(dispatch) == 24
        assert "total_revenue" in metrics
        assert summary["total_assets"] == 3
        assert summary["has_battery"] is True


if __name__ == "__main__":
    pytest.main([__file__])
