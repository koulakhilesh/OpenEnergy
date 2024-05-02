from abc import ABC, abstractmethod


class EfficiencyAdjuster(ABC):
    @abstractmethod
    def adjust_efficiency(self, temperature_c, charge_efficiency, discharge_efficiency):
        pass


class TemperatureEfficiencyAdjuster(EfficiencyAdjuster):
    def adjust_efficiency(self, temperature_c, charge_efficiency, discharge_efficiency):
        temp_effect = abs(temperature_c - 25) * 0.01
        new_charge_efficiency = max(0.5, min(charge_efficiency - temp_effect, 1.0))
        new_discharge_efficiency = max(0.5, min(discharge_efficiency - temp_effect, 1.0))
        return new_charge_efficiency, new_discharge_efficiency
    
class SOHCalculator(ABC):
    @abstractmethod
    def calculate_soh(self, soh, energy_cycled_mwh, dod):
        pass

class BasicSOHCalculator(SOHCalculator):
    def calculate_soh(self, soh, energy_cycled_mwh, dod):
        base_degradation = 0.000005
        dod_factor = 2 if dod > 0.5 else 1
        degradation_rate = base_degradation * energy_cycled_mwh * dod_factor
        return soh * (1 - degradation_rate)

class Battery:
    def __init__(self, capacity_mwh, charge_efficiency=0.9, discharge_efficiency=0.9, efficiency_adjuster=None, soh_calculator=None, **kwargs):
        self.validate_initial_conditions(capacity_mwh, kwargs.get("initial_soc", 0.5), kwargs.get("initial_soh", 1.0))
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
        self.efficiency_adjuster = efficiency_adjuster if efficiency_adjuster else TemperatureEfficiencyAdjuster()
        self.soh_calculator = soh_calculator if soh_calculator else BasicSOHCalculator()


    @staticmethod
    def validate_initial_conditions(capacity_mwh, initial_soc, initial_soh):
        if capacity_mwh <= 0:
            raise ValueError("Capacity must be greater than 0")
        if not (0 <= initial_soc <= 1):
            raise ValueError("Initial SOC must be between 0 and 1")
        if not (0 <= initial_soh <= 1):
            raise ValueError("Initial SOH must be between 0 and 1")

    def adjust_efficiency_for_temperature(self):
        self.charge_efficiency, self.discharge_efficiency = self.efficiency_adjuster.adjust_efficiency(self.temperature_c, self.charge_efficiency, self.discharge_efficiency)

    def charge(self, energy_mwh):
        self.adjust_efficiency_for_temperature()
        energy_mwh = min(energy_mwh, self.max_charge_rate_mw * self.duration_hours)
        actual_energy_mwh = energy_mwh * self.charge_efficiency
        self.soc = min(self.soc + actual_energy_mwh / self.capacity_mwh, 1.0)
        self.update_soh_and_cycles(energy_mwh)

    def discharge(self, energy_mwh):
        self.adjust_efficiency_for_temperature()
        energy_mwh = min(energy_mwh, self.max_discharge_rate_mw * self.duration_hours)
        actual_energy_mwh = energy_mwh * self.discharge_efficiency
        self.soc = max(self.soc - actual_energy_mwh / self.capacity_mwh, 0.0)
        self.update_soh_and_cycles(energy_mwh)

    def update_soh_and_cycles(self, energy_mwh):
        self.energy_cycled_mwh += energy_mwh
        dod = 1.0 - self.soc
        self.soh = self.soh_calculator.calculate_soh(self.soh, energy_mwh, dod)
        self.check_and_update_cycles()

    def check_and_update_cycles(self):
        cycles = (self.energy_cycled_mwh /(2*self.capacity_mwh))
        self.cycle_count += cycles
        self.last_cycle_soc = self.soc

        