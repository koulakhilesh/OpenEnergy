import os
import sys
import pytest
import math

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from scripts.assets.wind_system import WindSystem


class TestWindSystem:
    """Test cases for WindSystem class."""

    def test_initialization_default_params(self):
        """Test wind system initialization with default parameters."""
        wind_system = WindSystem(capacity_mw=2.0)
        
        assert wind_system.capacity_mw == 2.0
        assert wind_system.initial_efficiency == 1.0
        assert wind_system.degradation_rate_per_year == 0.005
        assert wind_system.duration_hours == 1.0
        assert wind_system.cut_in_speed == 3.0
        assert wind_system.rated_speed == 12.0
        assert wind_system.cut_out_speed == 25.0
        assert wind_system.hub_height == 80.0

    def test_initialization_custom_params(self):
        """Test wind system initialization with custom parameters."""
        wind_system = WindSystem(
            capacity_mw=5.0,
            initial_efficiency=0.95,
            degradation_rate_per_year=0.007,
            duration_hours=2.0,
            cut_in_speed=3.5,
            rated_speed=14.0,
            cut_out_speed=30.0,
            hub_height=100.0
        )
        
        assert wind_system.capacity_mw == 5.0
        assert wind_system.initial_efficiency == 0.95
        assert wind_system.degradation_rate_per_year == 0.007
        assert wind_system.duration_hours == 2.0
        assert wind_system.cut_in_speed == 3.5
        assert wind_system.rated_speed == 14.0
        assert wind_system.cut_out_speed == 30.0
        assert wind_system.hub_height == 100.0

    def test_initialization_invalid_capacity(self):
        """Test that invalid capacity raises assertion error."""
        with pytest.raises(AssertionError, match="Capacity must be positive"):
            WindSystem(capacity_mw=0)
        
        with pytest.raises(AssertionError, match="Capacity must be positive"):
            WindSystem(capacity_mw=-1.0)

    def test_initialization_invalid_efficiency(self):
        """Test that invalid efficiency raises assertion error."""
        with pytest.raises(AssertionError, match="Initial efficiency must be between 0 and 1"):
            WindSystem(capacity_mw=2.0, initial_efficiency=0)
        
        with pytest.raises(AssertionError, match="Initial efficiency must be between 0 and 1"):
            WindSystem(capacity_mw=2.0, initial_efficiency=1.5)

    def test_initialization_invalid_degradation_rate(self):
        """Test that invalid degradation rate raises assertion error."""
        with pytest.raises(AssertionError, match="Degradation rate must be between 0 and 1"):
            WindSystem(capacity_mw=2.0, degradation_rate_per_year=-0.1)
        
        with pytest.raises(AssertionError, match="Degradation rate must be between 0 and 1"):
            WindSystem(capacity_mw=2.0, degradation_rate_per_year=1.0)

    def test_initialization_invalid_duration(self):
        """Test that invalid duration raises assertion error."""
        with pytest.raises(AssertionError, match="Duration hours must be positive"):
            WindSystem(capacity_mw=2.0, duration_hours=-1.0)

    def test_initialization_invalid_wind_speeds(self):
        """Test that invalid wind speed configuration raises assertion error."""
        with pytest.raises(AssertionError, match="Wind speeds must be in logical order"):
            WindSystem(capacity_mw=2.0, cut_in_speed=15.0, rated_speed=12.0)
        
        with pytest.raises(AssertionError, match="Wind speeds must be in logical order"):
            WindSystem(capacity_mw=2.0, rated_speed=30.0, cut_out_speed=25.0)

    def test_initialization_invalid_hub_height(self):
        """Test that invalid hub height raises assertion error."""
        with pytest.raises(AssertionError, match="Hub height must be positive"):
            WindSystem(capacity_mw=2.0, hub_height=0)
        
        with pytest.raises(AssertionError, match="Hub height must be positive"):
            WindSystem(capacity_mw=2.0, hub_height=-10.0)

    def test_calculate_generation_basic(self):
        """Test basic generation calculation."""
        wind_system = WindSystem(capacity_mw=2.0)
        
        # Test at rated wind speed (should produce full power)
        generation = wind_system.calculate_generation(wind_speed_m_per_s=12.0, hours=1.0)
        expected = 2.0 * 1.0 * 1.0 * 1.0  # capacity * power_ratio * efficiency * hours
        assert generation == expected

    def test_calculate_generation_zero_wind(self):
        """Test generation with zero wind speed."""
        wind_system = WindSystem(capacity_mw=2.0)
        
        generation = wind_system.calculate_generation(wind_speed_m_per_s=0.0, hours=1.0)
        assert generation == 0.0

    def test_calculate_generation_below_cut_in(self):
        """Test generation below cut-in speed."""
        wind_system = WindSystem(capacity_mw=2.0, cut_in_speed=3.0)
        
        generation = wind_system.calculate_generation(wind_speed_m_per_s=2.0, hours=1.0)
        assert generation == 0.0

    def test_calculate_generation_above_cut_out(self):
        """Test generation above cut-out speed."""
        wind_system = WindSystem(capacity_mw=2.0, cut_out_speed=25.0)
        
        generation = wind_system.calculate_generation(wind_speed_m_per_s=30.0, hours=1.0)
        assert generation == 0.0

    def test_calculate_generation_cubic_curve(self):
        """Test generation with wind speed in cubic curve region."""
        wind_system = WindSystem(capacity_mw=2.0, cut_in_speed=3.0, rated_speed=12.0)
        
        # Test at mid-range wind speed
        wind_speed = 7.5  # Halfway between cut-in and rated
        generation = wind_system.calculate_generation(wind_speed_m_per_s=wind_speed, hours=1.0)
        
        # Calculate expected power ratio
        normalized_speed = (wind_speed - 3.0) / (12.0 - 3.0)  # 0.5
        expected_power_ratio = normalized_speed ** 3  # 0.125
        expected_generation = 2.0 * expected_power_ratio * 1.0 * 1.0
        
        assert abs(generation - expected_generation) < 1e-6

    def test_calculate_generation_different_hours(self):
        """Test generation calculation with different hours."""
        wind_system = WindSystem(capacity_mw=2.0)
        
        generation_1h = wind_system.calculate_generation(wind_speed_m_per_s=12.0, hours=1.0)
        generation_2h = wind_system.calculate_generation(wind_speed_m_per_s=12.0, hours=2.0)
        generation_half = wind_system.calculate_generation(wind_speed_m_per_s=12.0, hours=0.5)
        
        assert generation_2h == 2 * generation_1h
        assert generation_half == 0.5 * generation_1h

    def test_calculate_generation_invalid_inputs(self):
        """Test that invalid inputs raise assertion errors."""
        wind_system = WindSystem(capacity_mw=2.0)
        
        with pytest.raises(AssertionError, match="Wind speed must be non-negative"):
            wind_system.calculate_generation(wind_speed_m_per_s=-1.0, hours=1.0)
        
        with pytest.raises(AssertionError, match="Hours must be non-negative"):
            wind_system.calculate_generation(wind_speed_m_per_s=10.0, hours=-1.0)

    def test_assess_degradation_no_degradation(self):
        """Test degradation assessment with zero years."""
        wind_system = WindSystem(capacity_mw=2.0, initial_efficiency=0.95)
        
        efficiency = wind_system.assess_degradation(years=0.0)
        assert efficiency == 0.95

    def test_assess_degradation_one_year(self):
        """Test degradation after one year."""
        wind_system = WindSystem(capacity_mw=2.0, initial_efficiency=1.0, degradation_rate_per_year=0.01)
        
        efficiency = wind_system.assess_degradation(years=1.0)
        expected = 1.0 * (1 - 0.01) ** 1.0  # 0.99
        assert abs(efficiency - expected) < 1e-6

    def test_assess_degradation_multiple_years(self):
        """Test degradation after multiple years."""
        wind_system = WindSystem(capacity_mw=2.0, initial_efficiency=1.0, degradation_rate_per_year=0.005)
        
        efficiency = wind_system.assess_degradation(years=10.0)
        expected = 1.0 * (1 - 0.005) ** 10.0
        assert abs(efficiency - expected) < 1e-6

    def test_assess_degradation_extreme_case(self):
        """Test degradation that would go below zero."""
        wind_system = WindSystem(capacity_mw=2.0, initial_efficiency=1.0, degradation_rate_per_year=0.5)
        
        efficiency = wind_system.assess_degradation(years=10.0)
        # Should be capped at 0, but with 50% degradation rate, it might be very small but not exactly 0
        # (1 - 0.5)^10 = 0.0009765625
        assert efficiency >= 0.0
        assert efficiency < 0.01  # Should be very small

    def test_assess_degradation_invalid_years(self):
        """Test that negative years raises assertion error."""
        wind_system = WindSystem(capacity_mw=2.0)
        
        with pytest.raises(AssertionError, match="Years must be non-negative"):
            wind_system.assess_degradation(years=-1.0)

    def test_get_power_curve(self):
        """Test power curve generation."""
        wind_system = WindSystem(
            capacity_mw=2.0,
            cut_in_speed=3.0,
            rated_speed=12.0,
            cut_out_speed=25.0
        )
        
        power_curve = wind_system.get_power_curve()
        
        # Check that it's a dictionary
        assert isinstance(power_curve, dict)
        
        # Check specific wind speeds (power curve goes from 0 to cut_out_speed + 5)
        assert power_curve[0] == 0.0  # Below cut-in
        assert power_curve[2] == 0.0  # Below cut-in
        assert power_curve[12] == 1.0  # At rated speed
        assert power_curve[15] == 1.0  # Between rated and cut-out
        assert power_curve[25] == 0.0  # At cut-out
        # Power curve only goes up to cut_out_speed + 5 = 30, so 30 should be included
        if 30 in power_curve:
            assert power_curve[30] == 0.0  # Above cut-out
        
        # Check that curve is monotonic in the cubic region
        assert power_curve[4] < power_curve[6] < power_curve[8] < power_curve[10]

    def test_power_output_ratio_below_cut_in(self):
        """Test power output ratio below cut-in speed."""
        wind_system = WindSystem(capacity_mw=2.0, cut_in_speed=3.0)
        
        ratio = wind_system._get_power_output_ratio(2.0)
        assert ratio == 0.0

    def test_power_output_ratio_above_cut_out(self):
        """Test power output ratio above cut-out speed."""
        wind_system = WindSystem(capacity_mw=2.0, cut_out_speed=25.0)
        
        ratio = wind_system._get_power_output_ratio(30.0)
        assert ratio == 0.0

    def test_power_output_ratio_rated_region(self):
        """Test power output ratio in rated region."""
        wind_system = WindSystem(capacity_mw=2.0, rated_speed=12.0, cut_out_speed=25.0)
        
        ratio_at_rated = wind_system._get_power_output_ratio(12.0)
        ratio_above_rated = wind_system._get_power_output_ratio(20.0)
        
        assert ratio_at_rated == 1.0
        assert ratio_above_rated == 1.0

    def test_power_output_ratio_cubic_region(self):
        """Test power output ratio in cubic region."""
        wind_system = WindSystem(capacity_mw=2.0, cut_in_speed=3.0, rated_speed=12.0)
        
        # Test specific point in cubic region
        wind_speed = 6.0  # One-third from cut-in to rated
        normalized_speed = (6.0 - 3.0) / (12.0 - 3.0)  # 1/3
        expected_ratio = normalized_speed ** 3  # (1/3)^3 = 1/27
        
        ratio = wind_system._get_power_output_ratio(wind_speed)
        assert abs(ratio - expected_ratio) < 1e-6

    def test_calculate_capacity_factor_below_cut_in(self):
        """Test capacity factor below cut-in speed."""
        wind_system = WindSystem(capacity_mw=2.0, cut_in_speed=3.0)
        
        cf = wind_system.calculate_capacity_factor(average_wind_speed=2.0)
        assert cf == 0.0

    def test_calculate_capacity_factor_above_rated(self):
        """Test capacity factor above rated speed."""
        wind_system = WindSystem(capacity_mw=2.0, rated_speed=12.0)
        
        cf = wind_system.calculate_capacity_factor(average_wind_speed=15.0)
        assert cf == 0.9

    def test_calculate_capacity_factor_below_rated(self):
        """Test capacity factor below rated speed."""
        wind_system = WindSystem(capacity_mw=2.0, rated_speed=12.0)
        
        # Test at half rated speed
        cf = wind_system.calculate_capacity_factor(average_wind_speed=6.0)
        normalized_speed = 6.0 / 12.0  # 0.5
        expected_cf = min(0.9, normalized_speed * 0.4)  # min(0.9, 0.2) = 0.2
        
        assert cf == expected_cf

    def test_adjust_for_air_density_standard_conditions(self):
        """Test air density adjustment at standard conditions."""
        wind_system = WindSystem(capacity_mw=2.0)
        
        # Standard conditions: 15°C, 1013.25 hPa
        density_ratio = wind_system.adjust_for_air_density(
            temperature_c=15.0,
            pressure_hpa=1013.25
        )
        
        # Should be very close to 1.0 at standard conditions
        assert abs(density_ratio - 1.0) < 1e-6

    def test_adjust_for_air_density_cold_conditions(self):
        """Test air density adjustment in cold conditions."""
        wind_system = WindSystem(capacity_mw=2.0)
        
        # Cold conditions increase air density
        density_ratio = wind_system.adjust_for_air_density(
            temperature_c=-10.0,
            pressure_hpa=1020.0
        )
        
        # Should be greater than 1.0 (denser air)
        assert density_ratio > 1.0

    def test_adjust_for_air_density_hot_conditions(self):
        """Test air density adjustment in hot conditions."""
        wind_system = WindSystem(capacity_mw=2.0)
        
        # Hot conditions decrease air density
        density_ratio = wind_system.adjust_for_air_density(
            temperature_c=35.0,
            pressure_hpa=1000.0
        )
        
        # Should be less than 1.0 (less dense air)
        assert density_ratio < 1.0

    def test_adjust_for_air_density_high_altitude(self):
        """Test air density adjustment at high altitude (low pressure)."""
        wind_system = WindSystem(capacity_mw=2.0)
        
        # High altitude conditions (low pressure)
        density_ratio = wind_system.adjust_for_air_density(
            temperature_c=15.0,
            pressure_hpa=900.0
        )
        
        # Should be less than 1.0 (less dense air at altitude)
        assert density_ratio < 1.0

    def test_realistic_wind_scenario(self):
        """Test a realistic wind generation scenario."""
        wind_system = WindSystem(
            capacity_mw=2.5,
            initial_efficiency=0.98,
            cut_in_speed=3.0,
            rated_speed=12.0,
            cut_out_speed=25.0
        )
        
        # Test various wind speeds
        test_cases = [
            (0.0, 0.0),     # No wind
            (2.0, 0.0),     # Below cut-in
            (6.0, None),    # Cubic region (calculate expected)
            (12.0, 2.45),   # Rated speed: 2.5 MW * 0.98 efficiency
            (20.0, 2.45),   # Above rated
            (30.0, 0.0),    # Above cut-out
        ]
        
        for wind_speed, expected_generation in test_cases:
            generation = wind_system.calculate_generation(wind_speed, 1.0)
            
            if expected_generation is None:
                # Calculate expected for cubic region
                normalized_speed = (wind_speed - 3.0) / (12.0 - 3.0)
                power_ratio = normalized_speed ** 3
                expected_generation = 2.5 * power_ratio * 0.98
            
            assert abs(generation - expected_generation) < 1e-6, (
                f"Wind speed {wind_speed}: expected {expected_generation}, got {generation}"
            )

    def test_integration_with_degradation_and_air_density(self):
        """Test integration of generation with degradation and air density."""
        wind_system = WindSystem(
            capacity_mw=2.0,
            initial_efficiency=1.0,
            degradation_rate_per_year=0.01
        )
        
        # Calculate generation after 5 years with air density adjustment
        years = 5.0
        current_efficiency = wind_system.assess_degradation(years)
        
        # Generate at rated speed with hot conditions
        base_generation = wind_system.calculate_generation(12.0, 1.0)  # 2.0 MWh
        
        # Apply degradation
        degraded_generation = base_generation * (current_efficiency / wind_system.initial_efficiency)
        
        # Apply air density correction
        air_density_factor = wind_system.adjust_for_air_density(30.0, 1000.0)
        final_generation = degraded_generation * air_density_factor
        
        # Verify the calculation chain
        expected_efficiency = (1 - 0.01) ** 5  # ~0.951
        expected_degraded = 2.0 * expected_efficiency
        
        assert abs(degraded_generation - expected_degraded) < 1e-6
        assert final_generation < degraded_generation  # Hot conditions reduce output
        assert final_generation > 0  # Still generating power
