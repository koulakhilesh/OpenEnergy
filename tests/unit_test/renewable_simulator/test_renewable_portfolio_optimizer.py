import os
import sys
import datetime
from unittest.mock import Mock, patch, MagicMock
import pytest

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from scripts.renewable_simulator.renewable_portfolio_optimizer import RenewablePortfolioOptimizer
from scripts.renewable_simulator.interfaces import IRenewableOptimizer
from scripts.shared import Logger


@pytest.fixture
def optimizer():
    """Fixture for renewable portfolio optimizer."""
    return RenewablePortfolioOptimizer()


@pytest.fixture
def optimizer_with_debug():
    """Fixture for optimizer with debug logging."""
    return RenewablePortfolioOptimizer(logger_level=Logger.DEBUG)


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


@pytest.fixture
def sample_solar_generation():
    """Fixture for sample solar generation pattern."""
    return [0, 0, 0, 0, 0, 0, 10, 30, 50, 70, 85, 95,
            95, 85, 70, 50, 30, 10, 0, 0, 0, 0, 0, 0]


@pytest.fixture
def sample_wind_generation():
    """Fixture for sample wind generation pattern."""
    return [40, 35, 30, 25, 20, 25, 30, 35, 40, 45, 50, 55,
            60, 55, 50, 45, 40, 35, 30, 25, 20, 25, 30, 35]


# Tests for RenewablePortfolioOptimizer
class TestRenewablePortfolioOptimizer:
    
    def test_initialization_default(self):
        """Test optimizer initialization with default parameters."""
        optimizer = RenewablePortfolioOptimizer()
        
        assert hasattr(optimizer, 'logger')
        assert isinstance(optimizer.logger, Logger)

    def test_initialization_custom_logger_level(self):
        """Test optimizer initialization with custom logger level."""
        optimizer = RenewablePortfolioOptimizer(logger_level=Logger.DEBUG)
        
        assert hasattr(optimizer, 'logger')
        assert isinstance(optimizer.logger, Logger)

    def test_interface_compliance(self, optimizer):
        """Test that optimizer implements IRenewableOptimizer interface."""
        assert isinstance(optimizer, IRenewableOptimizer)
        assert hasattr(optimizer, 'optimize_portfolio')
        assert callable(optimizer.optimize_portfolio)

    @patch('scripts.renewable_simulator.renewable_portfolio_optimizer.pyo.SolverFactory')
    def test_optimize_portfolio_successful_optimization(
        self, mock_solver_factory, optimizer, test_date, sample_prices,
        sample_solar_generation, sample_wind_generation
    ):
        """Test successful portfolio optimization."""
        # Mock the solver and results
        mock_solver = Mock()
        mock_solver_factory.return_value = mock_solver
        
        mock_results = Mock()
        mock_results.solver.termination_condition = Mock()
        # Mock the termination condition enum value
        with patch('scripts.renewable_simulator.renewable_portfolio_optimizer.pyo.TerminationCondition') as mock_tc:
            mock_tc.optimal = "optimal"
            mock_results.solver.termination_condition = "optimal"
            mock_solver.solve.return_value = mock_results
            
            # Mock model values for _extract_results
            with patch.object(optimizer, '_extract_results') as mock_extract:
                expected_results = {
                    "date": test_date,
                    "optimal_value": 50000.0,
                    "dispatch_schedule": [],
                    "summary": {}
                }
                mock_extract.return_value = expected_results
                
                result = optimizer.optimize_portfolio(
                    solar_capacity=100.0,
                    wind_capacity=150.0,
                    battery_capacity=50.0,
                    prices=sample_prices,
                    date=test_date,
                    solar_generation=sample_solar_generation,
                    wind_generation=sample_wind_generation,
                )
                
                assert result == expected_results
                mock_solver_factory.assert_called_once_with("glpk")
                mock_solver.solve.assert_called_once()

    @patch('scripts.renewable_simulator.renewable_portfolio_optimizer.pyo.SolverFactory')
    def test_optimize_portfolio_optimization_failed(
        self, mock_solver_factory, optimizer, test_date, sample_prices
    ):
        """Test portfolio optimization when solver fails."""
        # Mock the solver to return non-optimal result
        mock_solver = Mock()
        mock_solver_factory.return_value = mock_solver
        
        mock_results = Mock()
        mock_results.solver.termination_condition = "infeasible"
        mock_solver.solve.return_value = mock_results
        
        with patch.object(optimizer, '_get_heuristic_solution') as mock_heuristic:
            expected_heuristic = {
                "date": test_date,
                "optimal_value": 25000.0,
                "dispatch_schedule": [],
                "summary": {}
            }
            mock_heuristic.return_value = expected_heuristic
            
            result = optimizer.optimize_portfolio(
                solar_capacity=100.0,
                wind_capacity=150.0,
                battery_capacity=50.0,
                prices=sample_prices,
                date=test_date,
            )
            
            assert result == expected_heuristic
            mock_heuristic.assert_called_once()

    @patch('scripts.renewable_simulator.renewable_portfolio_optimizer.pyo.SolverFactory')
    def test_optimize_portfolio_exception_handling(
        self, mock_solver_factory, optimizer, test_date, sample_prices
    ):
        """Test portfolio optimization exception handling."""
        # Make solver factory raise exception
        mock_solver_factory.side_effect = Exception("Solver not found")
        
        with patch.object(optimizer, '_get_heuristic_solution') as mock_heuristic:
            expected_heuristic = {
                "date": test_date,
                "optimal_value": 25000.0,
                "dispatch_schedule": [],
                "summary": {}
            }
            mock_heuristic.return_value = expected_heuristic
            
            result = optimizer.optimize_portfolio(
                solar_capacity=100.0,
                wind_capacity=150.0,
                battery_capacity=50.0,
                prices=sample_prices,
                date=test_date,
            )
            
            assert result == expected_heuristic
            mock_heuristic.assert_called_once()

    def test_optimize_portfolio_default_generation(
        self, optimizer, test_date, sample_prices
    ):
        """Test portfolio optimization with default generation values."""
        # Mock solver to fail so it uses heuristic
        with patch('scripts.renewable_simulator.renewable_portfolio_optimizer.pyo.SolverFactory') as mock_solver_factory:
            mock_solver = Mock()
            mock_solver_factory.return_value = mock_solver
            mock_solver.solve.side_effect = Exception("No solver available")
            
            result = optimizer.optimize_portfolio(
                solar_capacity=100.0,
                wind_capacity=150.0,
                battery_capacity=50.0,
                prices=sample_prices,
                date=test_date,
                # No generation provided - should use defaults
            )
            
            assert "optimal_value" in result
            assert "dispatch_schedule" in result
            assert result["date"] == test_date

    @patch('scripts.renewable_simulator.renewable_portfolio_optimizer.pyo')
    def test_build_portfolio_model(self, mock_pyo, optimizer):
        """Test building the optimization model."""
        # Mock the pyomo components
        mock_model = Mock()
        mock_pyo.ConcreteModel.return_value = mock_model
        mock_pyo.RangeSet.return_value = range(24)
        mock_pyo.Var.return_value = Mock()
        mock_pyo.Param.return_value = Mock()
        mock_pyo.Objective.return_value = Mock()
        mock_pyo.Constraint.return_value = Mock()
        
        # Test the model building
        model = optimizer._build_portfolio_model(
            solar_capacity=100.0,
            wind_capacity=150.0,
            battery_capacity=50.0,
            prices=[50.0] * 24,
            solar_generation=[30.0] * 24,
            wind_generation=[40.0] * 24,
        )
        
        assert model == mock_model
        mock_pyo.ConcreteModel.assert_called_once()

    @patch('scripts.renewable_simulator.renewable_portfolio_optimizer.pyo')
    def test_extract_results(self, mock_pyo, optimizer, test_date):
        """Test extracting results from solved model."""
        # Mock the model with solved values
        mock_model = Mock()
        mock_model.T = range(24)
        mock_model.objective = Mock()
        
        # Mock pyo.value to return specific values
        def mock_pyo_value(var):
            if hasattr(var, '_mock_name'):
                if 'solar_dispatch' in var._mock_name:
                    return 50.0
                elif 'wind_dispatch' in var._mock_name:
                    return 60.0
                elif 'battery_charge' in var._mock_name:
                    return 10.0
                elif 'battery_discharge' in var._mock_name:
                    return 5.0
                elif 'battery_soc' in var._mock_name:
                    return 25.0
                elif 'prices' in var._mock_name:
                    return 75.0
            return 0.0
        
        # Create mock variables with names
        for t in range(24):
            solar_var = Mock()
            solar_var._mock_name = f'solar_dispatch_{t}'
            setattr(mock_model, f'solar_dispatch', {t: solar_var})
            
            wind_var = Mock()
            wind_var._mock_name = f'wind_dispatch_{t}'
            setattr(mock_model, f'wind_dispatch', {t: wind_var})
            
            charge_var = Mock()
            charge_var._mock_name = f'battery_charge_{t}'
            setattr(mock_model, f'battery_charge', {t: charge_var})
            
            discharge_var = Mock()
            discharge_var._mock_name = f'battery_discharge_{t}'
            setattr(mock_model, f'battery_discharge', {t: discharge_var})
            
            soc_var = Mock()
            soc_var._mock_name = f'battery_soc_{t}'
            setattr(mock_model, f'battery_soc', {t: soc_var})
            
            price_var = Mock()
            price_var._mock_name = f'prices_{t}'
            setattr(mock_model, f'prices', {t: price_var})
        
        mock_pyo.value.side_effect = mock_pyo_value
        
        # Mock the model variables to return Mock objects with the mock_value function
        mock_model.solar_dispatch = {t: Mock() for t in range(24)}
        mock_model.wind_dispatch = {t: Mock() for t in range(24)}
        mock_model.battery_charge = {t: Mock() for t in range(24)}
        mock_model.battery_discharge = {t: Mock() for t in range(24)}
        mock_model.battery_soc = {t: Mock() for t in range(24)}
        mock_model.prices = {t: Mock() for t in range(24)}
        
        # Add names to mocks for identification
        for t in range(24):
            mock_model.solar_dispatch[t]._mock_name = f'solar_dispatch_{t}'
            mock_model.wind_dispatch[t]._mock_name = f'wind_dispatch_{t}'
            mock_model.battery_charge[t]._mock_name = f'battery_charge_{t}'
            mock_model.battery_discharge[t]._mock_name = f'battery_discharge_{t}'
            mock_model.battery_soc[t]._mock_name = f'battery_soc_{t}'
            mock_model.prices[t]._mock_name = f'prices_{t}'
        
        mock_model.objective._mock_name = 'objective'
        mock_pyo.value.return_value = 50000.0  # Default return for objective
        
        results = optimizer._extract_results(mock_model, test_date)
        
        assert isinstance(results, dict)
        assert results["date"] == test_date
        assert "optimal_value" in results
        assert "dispatch_schedule" in results
        assert "summary" in results
        assert len(results["dispatch_schedule"]) == 24

    def test_get_heuristic_solution(
        self, optimizer, test_date, sample_prices,
        sample_solar_generation, sample_wind_generation
    ):
        """Test getting heuristic solution."""
        result = optimizer._get_heuristic_solution(
            solar_capacity=100.0,
            wind_capacity=150.0,
            battery_capacity=50.0,
            prices=sample_prices,
            date=test_date,
            solar_generation=sample_solar_generation,
            wind_generation=sample_wind_generation,
        )
        
        assert isinstance(result, dict)
        assert result["date"] == test_date
        assert "optimal_value" in result
        assert "dispatch_schedule" in result
        assert "summary" in result
        
        dispatch_schedule = result["dispatch_schedule"]
        assert len(dispatch_schedule) == 24
        
        # Check first hour
        first_hour = dispatch_schedule[0]
        assert first_hour["hour"] == 0
        assert first_hour["solar_dispatch_mw"] == 0  # No solar at night
        assert first_hour["wind_dispatch_mw"] == 40  # Wind available
        assert first_hour["battery_charge_mw"] == 0  # No battery optimization
        assert first_hour["battery_discharge_mw"] == 0
        
        # Check summary
        summary = result["summary"]
        expected_keys = [
            "total_solar_dispatch_mwh", "total_wind_dispatch_mwh",
            "total_battery_charge_mwh", "total_battery_discharge_mwh",
            "total_revenue", "battery_efficiency"
        ]
        for key in expected_keys:
            assert key in summary

    def test_get_heuristic_solution_empty_generation(
        self, optimizer, test_date, sample_prices
    ):
        """Test heuristic solution with empty generation lists."""
        result = optimizer._get_heuristic_solution(
            solar_capacity=100.0,
            wind_capacity=150.0,
            battery_capacity=50.0,
            prices=sample_prices,
            date=test_date,
            solar_generation=[],
            wind_generation=[],
        )
        
        assert len(result["dispatch_schedule"]) == 24
        
        # All generation should be zero
        for hour_data in result["dispatch_schedule"]:
            assert hour_data["solar_dispatch_mw"] == 0
            assert hour_data["wind_dispatch_mw"] == 0

    def test_get_heuristic_solution_mismatched_lengths(
        self, optimizer, test_date
    ):
        """Test heuristic solution with mismatched data lengths."""
        short_prices = [50.0] * 12
        short_solar = [30.0] * 6
        short_wind = [40.0] * 18
        
        result = optimizer._get_heuristic_solution(
            solar_capacity=100.0,
            wind_capacity=150.0,
            battery_capacity=50.0,
            prices=short_prices,
            date=test_date,
            solar_generation=short_solar,
            wind_generation=short_wind,
        )
        
        assert len(result["dispatch_schedule"]) == 24
        
        # Check handling of different length arrays
        dispatch = result["dispatch_schedule"]
        
        # Hours 0-5 should have solar generation
        for hour in range(6):
            assert dispatch[hour]["solar_dispatch_mw"] == 30.0
        
        # Hours 6-23 should have no solar (beyond array length)
        for hour in range(6, 24):
            assert dispatch[hour]["solar_dispatch_mw"] == 0
        
        # Hours 0-17 should have wind generation
        for hour in range(18):
            assert dispatch[hour]["wind_dispatch_mw"] == 40.0
        
        # Hours 18-23 should have no wind (beyond array length)
        for hour in range(18, 24):
            assert dispatch[hour]["wind_dispatch_mw"] == 0
        
        # Hours 0-11 should use provided prices
        for hour in range(12):
            assert dispatch[hour]["price"] == 50.0
        
        # Hours 12-23 should use last price
        for hour in range(12, 24):
            assert dispatch[hour]["price"] == 50.0

    @pytest.mark.parametrize(
        "solar_cap, wind_cap, battery_cap",
        [
            (100.0, 150.0, 50.0),
            (0.0, 200.0, 0.0),
            (300.0, 0.0, 100.0),
            (50.0, 75.0, 25.0),
        ],
    )
    def test_optimize_portfolio_various_capacities(
        self, optimizer, test_date, sample_prices, solar_cap, wind_cap, battery_cap
    ):
        """Test portfolio optimization with various capacity combinations."""
        # Force solver to fail so it uses heuristic
        with patch('scripts.renewable_simulator.renewable_portfolio_optimizer.pyo.SolverFactory') as mock_solver_factory:
            mock_solver = Mock()
            mock_solver_factory.return_value = mock_solver
            mock_solver.solve.side_effect = Exception("No solver available")
            
            result = optimizer.optimize_portfolio(
                solar_capacity=solar_cap,
                wind_capacity=wind_cap,
                battery_capacity=battery_cap,
                prices=sample_prices,
                date=test_date,
            )
            
            assert "optimal_value" in result
            assert "dispatch_schedule" in result
            assert result["date"] == test_date

    @pytest.mark.parametrize(
        "test_date",
        [
            datetime.date(2024, 1, 1),   # New Year
            datetime.date(2024, 6, 21),  # Summer solstice
            datetime.date(2024, 12, 21), # Winter solstice
            datetime.date(2024, 2, 29),  # Leap year
        ],
    )
    def test_optimize_portfolio_various_dates(
        self, optimizer, test_date, sample_prices
    ):
        """Test portfolio optimization with various dates."""
        with patch.object(optimizer, '_get_heuristic_solution') as mock_heuristic:
            mock_heuristic.return_value = {
                "date": test_date,
                "optimal_value": 1000.0,
                "dispatch_schedule": [],
                "summary": {}
            }
            
            result = optimizer.optimize_portfolio(
                solar_capacity=100.0,
                wind_capacity=150.0,
                battery_capacity=50.0,
                prices=sample_prices,
                date=test_date,
            )
            
            assert result["date"] == test_date

    def test_heuristic_solution_capacity_constraints(
        self, optimizer, test_date, sample_prices
    ):
        """Test that heuristic solution respects capacity constraints."""
        # Create generation that exceeds capacity
        high_solar = [200.0] * 24  # Exceeds 100 MW capacity
        high_wind = [300.0] * 24   # Exceeds 150 MW capacity
        
        result = optimizer._get_heuristic_solution(
            solar_capacity=100.0,
            wind_capacity=150.0,
            battery_capacity=50.0,
            prices=sample_prices,
            date=test_date,
            solar_generation=high_solar,
            wind_generation=high_wind,
        )
        
        # Check that dispatch doesn't exceed capacity
        for hour_data in result["dispatch_schedule"]:
            assert hour_data["solar_dispatch_mw"] <= 100.0
            assert hour_data["wind_dispatch_mw"] <= 150.0

    def test_revenue_calculation_in_heuristic(
        self, optimizer, test_date
    ):
        """Test revenue calculation in heuristic solution."""
        prices = [100.0] * 24
        solar_gen = [50.0] * 24
        wind_gen = [30.0] * 24
        
        result = optimizer._get_heuristic_solution(
            solar_capacity=100.0,
            wind_capacity=150.0,
            battery_capacity=50.0,
            prices=prices,
            date=test_date,
            solar_generation=solar_gen,
            wind_generation=wind_gen,
        )
        
        # Each hour should generate 80 MW (50 solar + 30 wind) at 100 $/MWh
        expected_hourly_revenue = 80.0 * 100.0
        expected_total_revenue = expected_hourly_revenue * 24
        
        for hour_data in result["dispatch_schedule"]:
            assert hour_data["revenue"] == expected_hourly_revenue
        
        assert result["optimal_value"] == expected_total_revenue
        assert result["summary"]["total_revenue"] == expected_total_revenue

    def test_integration_with_logger(self, optimizer_with_debug):
        """Test integration with logger."""
        assert hasattr(optimizer_with_debug, 'logger')
        
        # Test that logger is used (we can't easily test actual logging output
        # but we can ensure the logger exists and has the right level)
        assert isinstance(optimizer_with_debug.logger, Logger)

    def test_edge_case_zero_capacities(self, optimizer, test_date, sample_prices):
        """Test edge case with zero capacities."""
        result = optimizer._get_heuristic_solution(
            solar_capacity=0.0,
            wind_capacity=0.0,
            battery_capacity=0.0,
            prices=sample_prices,
            date=test_date,
            solar_generation=[50.0] * 24,
            wind_generation=[30.0] * 24,
        )
        
        # All dispatch should be zero due to zero capacity
        for hour_data in result["dispatch_schedule"]:
            assert hour_data["solar_dispatch_mw"] == 0.0
            assert hour_data["wind_dispatch_mw"] == 0.0
            assert hour_data["net_export_mw"] == 0.0
            assert hour_data["revenue"] == 0.0
        
        assert result["optimal_value"] == 0.0

    def test_edge_case_empty_prices(self, optimizer, test_date):
        """Test edge case with empty price list."""
        result = optimizer._get_heuristic_solution(
            solar_capacity=100.0,
            wind_capacity=150.0,
            battery_capacity=50.0,
            prices=[],
            date=test_date,
            solar_generation=[50.0] * 24,
            wind_generation=[30.0] * 24,
        )
        
        # Should handle empty prices gracefully (using 0.0 as default)
        assert len(result["dispatch_schedule"]) == 24
        
        # All prices should be 0.0 when prices list is empty
        for hour_data in result["dispatch_schedule"]:
            assert hour_data["price"] == 0.0
            assert hour_data["revenue"] == 0.0  # No revenue with 0 price


if __name__ == "__main__":
    pytest.main([__file__])
