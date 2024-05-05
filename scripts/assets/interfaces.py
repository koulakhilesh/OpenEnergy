from abc import ABC, abstractmethod


class IEfficiencyAdjuster(ABC):
    @abstractmethod
    def adjust_efficiency(
        self,
        temperature_c: float,
        charge_efficiency: float,
        discharge_efficiency: float,
    ):
        pass


class ISOHCalculator(ABC):
    @abstractmethod
    def calculate_soh(self, soh: float, energy_cycled_mwh: float, dod: float):
        pass
