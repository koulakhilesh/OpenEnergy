from .interfaces import IWindSystem


class WindSystem(IWindSystem):
    """
    Implementation of a Wind Generation System.

    This class models a wind turbine or wind farm with realistic power curves,
    efficiency degradation, and environmental factors.
    """

    def __init__(
        self,
        capacity_mw: float,
        initial_efficiency: float = 1.0,
        degradation_rate_per_year: float = 0.005,  # Wind turbines degrade slower than PV
        duration_hours: float = 1.0,
        cut_in_speed: float = 3.0,  # m/s
        rated_speed: float = 12.0,  # m/s
        cut_out_speed: float = 25.0,  # m/s
        hub_height: float = 80.0,  # meters
    ):
        """
        Initialize a Wind System.

        Args:
            capacity_mw (float): Rated capacity in MW.
            initial_efficiency (float): Initial system efficiency (0-1).
            degradation_rate_per_year (float): Annual degradation rate (0-1).
            duration_hours (float): Operating duration in hours.
            cut_in_speed (float): Minimum wind speed for generation (m/s).
            rated_speed (float): Wind speed at rated power (m/s).
            cut_out_speed (float): Maximum safe wind speed (m/s).
            hub_height (float): Turbine hub height in meters.
        """
        assert capacity_mw > 0, "Capacity must be positive"
        assert 0 < initial_efficiency <= 1, "Initial efficiency must be between 0 and 1"
        assert 0 <= degradation_rate_per_year < 1, (
            "Degradation rate must be between 0 and 1"
        )
        assert duration_hours >= 0, "Duration hours must be positive"
        assert 0 < cut_in_speed < rated_speed < cut_out_speed, (
            "Wind speeds must be in logical order"
        )
        assert hub_height > 0, "Hub height must be positive"

        self.capacity_mw = capacity_mw
        self.initial_efficiency = initial_efficiency
        self.degradation_rate_per_year = degradation_rate_per_year
        self.duration_hours = duration_hours
        self.cut_in_speed = cut_in_speed
        self.rated_speed = rated_speed
        self.cut_out_speed = cut_out_speed
        self.hub_height = hub_height

    def calculate_generation(self, wind_speed_m_per_s: float, hours: float) -> float:
        """
        Calculate electricity generation based on wind speed and duration.

        Args:
            wind_speed_m_per_s (float): Wind speed in m/s.
            hours (float): Generation duration in hours.

        Returns:
            float: Generated electricity in MWh.
        """
        assert wind_speed_m_per_s >= 0, "Wind speed must be non-negative"
        assert hours >= 0, "Hours must be non-negative"

        # Get power output ratio from power curve
        power_ratio = self._get_power_output_ratio(wind_speed_m_per_s)

        # Calculate generation
        generation_mw = self.capacity_mw * power_ratio * self.initial_efficiency
        generation_mwh = generation_mw * hours

        return generation_mwh

    def assess_degradation(self, years: float) -> float:
        """
        Assess efficiency degradation over time.

        Args:
            years (float): Years of operation.

        Returns:
            float: Current efficiency as a decimal.
        """
        assert years >= 0, "Years must be non-negative"
        current_efficiency = max(
            0, self.initial_efficiency * (1 - self.degradation_rate_per_year) ** years
        )
        return current_efficiency

    def get_power_curve(self) -> dict:
        """
        Get the wind turbine power curve.

        Returns:
            dict: Mapping of wind speeds to power output ratios (0-1).
        """
        power_curve = {}

        # Generate power curve points
        for speed in range(0, int(self.cut_out_speed) + 5):
            power_curve[speed] = self._get_power_output_ratio(float(speed))

        return power_curve

    def _get_power_output_ratio(self, wind_speed: float) -> float:
        """
        Calculate power output ratio based on wind speed.

        Uses a realistic wind turbine power curve:
        - Below cut-in: 0% power
        - Cut-in to rated: Cubic increase to 100%
        - Rated to cut-out: 100% power
        - Above cut-out: 0% power

        Args:
            wind_speed (float): Wind speed in m/s.

        Returns:
            float: Power output ratio (0-1).
        """
        if wind_speed < self.cut_in_speed:
            # Below cut-in speed
            return 0.0
        elif wind_speed >= self.cut_out_speed:
            # Above cut-out speed (turbine shuts down for safety)
            return 0.0
        elif wind_speed >= self.rated_speed:
            # Between rated and cut-out speed (full power)
            return 1.0
        else:
            # Between cut-in and rated speed (cubic power curve)
            normalized_speed = (wind_speed - self.cut_in_speed) / (
                self.rated_speed - self.cut_in_speed
            )
            return normalized_speed**3

    def calculate_capacity_factor(self, average_wind_speed: float) -> float:
        """
        Calculate expected capacity factor based on average wind speed.

        Args:
            average_wind_speed (float): Average wind speed in m/s.

        Returns:
            float: Expected capacity factor (0-1).
        """
        if average_wind_speed < self.cut_in_speed:
            return 0.0
        elif average_wind_speed >= self.rated_speed:
            return 0.9  # High capacity factor for good wind sites
        else:
            # Simplified capacity factor estimation
            normalized_speed = average_wind_speed / self.rated_speed
            return min(0.9, normalized_speed * 0.4)  # Max ~40% for typical sites

    def adjust_for_air_density(
        self, temperature_c: float, pressure_hpa: float
    ) -> float:
        """
        Calculate air density correction factor.

        Wind power is proportional to air density, which varies with
        temperature and atmospheric pressure.

        Args:
            temperature_c (float): Temperature in Celsius.
            pressure_hpa (float): Atmospheric pressure in hPa.

        Returns:
            float: Air density correction factor (typically 0.8-1.2).
        """
        # Standard conditions: 15°C, 1013.25 hPa
        standard_temp_k = 288.15  # 15°C in Kelvin
        standard_pressure_pa = 101325  # 1013.25 hPa in Pa

        temp_k = temperature_c + 273.15
        pressure_pa = pressure_hpa * 100

        # Air density ratio using ideal gas law
        density_ratio = (pressure_pa / standard_pressure_pa) * (
            standard_temp_k / temp_k
        )

        return density_ratio
