from abc import ABC, abstractmethod


class IEfficiencyAdjuster(ABC):
    """Interface for adjusting efficiency based on temperature and charge/discharge efficiency."""

    @abstractmethod
    def adjust_efficiency(
        self,
        temperature_c: float,
        charge_efficiency: float,
        discharge_efficiency: float,
    ):
        """Adjusts the efficiency based on the given temperature and charge/discharge efficiency.

        Args:
            temperature_c (float): The temperature in degrees Celsius.
            charge_efficiency (float): The charge efficiency.
            discharge_efficiency (float): The discharge efficiency.

        Returns:
            None
        """
        pass


class ISOHCalculator(ABC):
    """
    Abstract base class for calculating State of Health (SOH) of a battery.

    This class defines the interface for calculating the SOH of a battery based on the energy cycled and depth of discharge.

    Attributes:
        None

    Methods:
        calculate_soh: Abstract method to calculate the SOH of a battery.

    """

    @abstractmethod
    def calculate_soh(self, soh: float, energy_cycled_mwh: float, dod: float):
        """
        Abstract method to calculate the State of Health (SOH) of a battery.

        Args:
            soh (float): The initial State of Health (SOH) of the battery.
            energy_cycled_mwh (float): The total energy cycled by the battery in megawatt-hours (MWh).
            dod (float): The depth of discharge (DOD) of the battery.

        Returns:
            None

        """
        pass


class IBatterySystem(ABC):
    """
    Interface for a battery object with various properties and methods for charging and discharging.

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

    Methods:
        adjust_efficiency_for_temperature: Adjusts the charge and discharge efficiencies based on temperature.
        charge: Charges the battery with the specified amount of energy.
        discharge: Discharges the battery with the specified amount of energy.
        update_soh_and_cycles: Updates the state of health (SOH) and cycle count based on the energy cycled.
        check_and_update_cycles: Checks and updates the cycle count based on the energy cycled.

    """

    @abstractmethod
    def adjust_efficiency_for_temperature(self):
        """Adjusts the charge and discharge efficiencies of the battery based on temperature."""
        pass

    @abstractmethod
    def charge(self, energy_mwh: float):
        """Charges the battery with the specified amount of energy.

        Args:
            energy_mwh (float): The amount of energy to be charged in megawatt-hours.
        """
        pass

    @abstractmethod
    def discharge(self, energy_mwh: float):
        """Discharges the battery with the specified amount of energy.

        Args:
            energy_mwh (float): The amount of energy to be discharged in megawatt-hours.

        """
        pass

    @abstractmethod
    def update_soh_and_cycles(self, energy_mwh: float):
        """Updates the state of health (SOH) and cycle count of the battery based on the energy cycled.

        Args:
            energy_mwh (float): The amount of energy cycled in megawatt-hours.
        """
        pass

    @abstractmethod
    def check_and_update_cycles(self):
        """Checks and updates the cycle count of the battery based on the energy cycled."""
        pass

class IPVSystem:
    """
    Interface for a Photovoltaic (PV) System.
    """
    def calculate_generation(self, irradiance_w_per_m2: float, hours: float) -> float:
        """
        Calculates the electricity generation based on solar irradiance and efficiency.
        """
        pass

    def assess_degradation(self, years: float) -> float:
        """
        Assesses the degradation of the PV system's efficiency over time.

        Args:
            years (float): The number of years the system has been in operation.

        Returns:
            float: The degraded efficiency as a decimal (e.g., 0.14 for 14% efficiency after degradation).
        """
        pass