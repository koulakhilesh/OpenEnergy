from .interfaces import IEfficiencyAdjuster, ISOHCalculator


class TemperatureEfficiencyAdjuster(IEfficiencyAdjuster):
    """
    Adjusts the efficiency of a battery based on the temperature.

    Args:
        temperature_c (float): The temperature in degrees Celsius.
        charge_efficiency (float): The current charge efficiency of the battery.
        discharge_efficiency (float): The current discharge efficiency of the battery.

    Returns:
        tuple: A tuple containing the adjusted charge efficiency and discharge efficiency.

    """

    def adjust_efficiency(
        self,
        temperature_c: float,
        charge_efficiency: float,
        discharge_efficiency: float,
    ):
        temp_effect = abs(temperature_c - 25) * 0.01
        new_charge_efficiency = max(0.5, min(charge_efficiency - temp_effect, 1.0))
        new_discharge_efficiency = max(
            0.5, min(discharge_efficiency - temp_effect, 1.0)
        )
        return new_charge_efficiency, new_discharge_efficiency


class BasicSOHCalculator(ISOHCalculator):
    """
    A basic State of Health (SOH) calculator implementation.

    This calculator calculates the SOH based on the energy cycled and depth of discharge (DOD).

    Attributes:
        None

    Methods:
        calculate_soh: Calculates the SOH based on the given parameters.

    """

    def calculate_soh(self, soh: float, energy_cycled_mwh: float, dod: float):
        """
        Calculates the State of Health (SOH) based on the given parameters.

        Args:
            soh (float): The initial State of Health.
            energy_cycled_mwh (float): The amount of energy cycled in megawatt-hours.
            dod (float): The depth of discharge as a fraction (0 to 1).

        Returns:
            float: The updated State of Health (SOH) after degradation.

        """
        base_degradation = 0.000005
        dod_factor = 2 if dod > 0.5 else 1
        degradation_rate = base_degradation * energy_cycled_mwh * dod_factor
        return soh * (1 - degradation_rate)


class Battery:
    """
    Represents a battery object with various properties and methods for charging and discharging.

    Args:
        capacity_mwh (float): The capacity of the battery in megawatt-hours.
        charge_efficiency (float, optional): The efficiency of the battery during charging. Defaults to 0.9.
        discharge_efficiency (float, optional): The efficiency of the battery during discharging. Defaults to 0.9.
        efficiency_adjuster (object, optional): An object that adjusts the efficiency based on temperature. Defaults to None.
        soh_calculator (object, optional): An object that calculates the state of health (SOH) of the battery. Defaults to None.
        **kwargs: Additional keyword arguments for configuring the battery.

    Attributes:
        capacity_mwh (float): The capacity of the battery in megawatt-hours.
        charge_efficiency (float): The efficiency of the battery during charging.
        discharge_efficiency (float): The efficiency of the battery during discharging.
        max_charge_rate_mw (float): The maximum charge rate of the battery in megawatts.
        max_discharge_rate_mw (float): The maximum discharge rate of the battery in megawatts.
        initial_soc (float): The initial state of charge (SOC) of the battery.
        soc (float): The current state of charge (SOC) of the battery.
        soh (float): The state of health (SOH) of the battery.
        temperature_c (float): The temperature of the battery in degrees Celsius.
        cycle_count (float): The number of charge-discharge cycles the battery has undergone.
        energy_cycled_mwh (float): The total energy cycled by the battery in megawatt-hours.
        duration_hours (float): The duration of the charging or discharging operation in hours.
        efficiency_adjuster (object): An object that adjusts the efficiency based on temperature.
        soh_calculator (object): An object that calculates the state of health (SOH) of the battery.
    """

    def __init__(
        self,
        capacity_mwh: float,
        charge_efficiency: float = 0.9,
        discharge_efficiency: float = 0.9,
        efficiency_adjuster=None,
        soh_calculator=None,
        **kwargs,
    ):
        self.validate_initial_conditions(
            capacity_mwh, kwargs.get("initial_soc", 0.5), kwargs.get("initial_soh", 1.0)
        )
        self.capacity_mwh = capacity_mwh
        self.charge_efficiency = charge_efficiency
        self.discharge_efficiency = discharge_efficiency
        self.max_charge_rate_mw = kwargs.get("max_charge_rate_mw", capacity_mwh)
        self.max_discharge_rate_mw = kwargs.get("max_discharge_rate_mw", capacity_mwh)
        self.initial_soc = kwargs.get("initial_soc", 0.5)
        self.soc = self.initial_soc
        self.soh = kwargs.get("initial_soh", 1.0)
        self.temperature_c = kwargs.get("temperature_c", 25)
        self.cycle_count = kwargs.get("starting_cycle_count", 0.0)
        self.energy_cycled_mwh = kwargs.get("starting_energy_cycled_mwh", 0.0)
        self.duration_hours = kwargs.get("duration_hours", 1.0)
        self.efficiency_adjuster = (
            efficiency_adjuster
            if efficiency_adjuster
            else TemperatureEfficiencyAdjuster()
        )
        self.soh_calculator = soh_calculator if soh_calculator else BasicSOHCalculator()

    @staticmethod
    def validate_initial_conditions(
        capacity_mwh: float, initial_soc: float, initial_soh: float
    ):
        """
        Validates the initial conditions of the battery.

        Args:
            capacity_mwh (float): The capacity of the battery in megawatt-hours.
            initial_soc (float): The initial state of charge (SOC) of the battery.
            initial_soh (float): The initial state of health (SOH) of the battery.

        Raises:
            ValueError: If the capacity is less than or equal to 0, or if the initial SOC or SOH is not between 0 and 1.
        """
        if capacity_mwh <= 0:
            raise ValueError("Capacity must be greater than 0")
        if not (0 <= initial_soc <= 1):
            raise ValueError("Initial SOC must be between 0 and 1")
        if not (0 <= initial_soh <= 1):
            raise ValueError("Initial SOH must be between 0 and 1")

    def adjust_efficiency_for_temperature(self):
        """
        Adjusts the charge and discharge efficiencies of the battery based on temperature.
        """
        (
            self.charge_efficiency,
            self.discharge_efficiency,
        ) = self.efficiency_adjuster.adjust_efficiency(
            self.temperature_c, self.charge_efficiency, self.discharge_efficiency
        )

    def charge(self, energy_mwh: float):
        """
        Charges the battery with the specified amount of energy.

        Args:
            energy_mwh (float): The amount of energy to be charged in megawatt-hours.
        """
        self.adjust_efficiency_for_temperature()
        energy_mwh = min(energy_mwh, self.max_charge_rate_mw * self.duration_hours)
        actual_energy_mwh = energy_mwh * self.charge_efficiency
        self.soc = min(self.soc + actual_energy_mwh / self.capacity_mwh, 1.0)
        self.update_soh_and_cycles(energy_mwh)

    def discharge(self, energy_mwh: float):
        """
        Discharges the battery with the specified amount of energy.

        Args:
            energy_mwh (float): The amount of energy to be discharged in megawatt-hours.
        """
        self.adjust_efficiency_for_temperature()
        energy_mwh = min(energy_mwh, self.max_discharge_rate_mw * self.duration_hours)
        actual_energy_mwh = energy_mwh * self.discharge_efficiency
        self.soc = max(self.soc - actual_energy_mwh / self.capacity_mwh, 0.0)
        self.update_soh_and_cycles(energy_mwh)

    def update_soh_and_cycles(self, energy_mwh: float):
        """
        Updates the state of health (SOH) and cycle count of the battery based on the energy cycled.

        Args:
            energy_mwh (float): The amount of energy cycled in megawatt-hours.
        """
        self.energy_cycled_mwh += energy_mwh
        dod = 1.0 - self.soc
        self.soh = self.soh_calculator.calculate_soh(self.soh, energy_mwh, dod)
        self.check_and_update_cycles()

    def check_and_update_cycles(self):
        """
        Checks and updates the cycle count of the battery based on the energy cycled.
        """
        cycles = self.energy_cycled_mwh / (2 * self.capacity_mwh)
        self.cycle_count += cycles
        self.last_cycle_soc = self.soc
