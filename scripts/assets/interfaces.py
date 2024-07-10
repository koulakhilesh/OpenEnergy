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
