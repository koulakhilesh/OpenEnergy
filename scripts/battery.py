from abc import ABC, abstractmethod

class EfficiencyAdjuster(ABC):
    """
    Abstract base class for adjusting charge and discharge efficiencies.
    """
    @abstractmethod
    def adjust_efficiency(self, temperature_c, charge_efficiency, discharge_efficiency):
        pass

class TemperatureEfficiencyAdjuster(EfficiencyAdjuster):
    """
    Adjusts charge and discharge efficiencies based on temperature.
    """
    def adjust_efficiency(self, temperature_c, charge_efficiency, discharge_efficiency):
        temp_effect = abs(temperature_c - 25) * 0.01
        new_charge_efficiency = max(0.5, min(charge_efficiency - temp_effect, 1.0))
        new_discharge_efficiency = max(0.5, min(discharge_efficiency - temp_effect, 1.0))
        return new_charge_efficiency, new_discharge_efficiency

class SOHCalculator(ABC):
    """
    Abstract base class for calculating the State of Health (SOH) of the battery.
    """
    @abstractmethod
    def calculate_soh(self, soh, energy_cycled_mwh, dod):
        pass

class BasicSOHCalculator(SOHCalculator):
    """
    Basic implementation of SOH calculation.
    """
    def calculate_soh(self, soh, energy_cycled_mwh, dod):
        base_degradation = 0.000005
        dod_factor = 2 if dod > 0.5 else 1
        degradation_rate = base_degradation * energy_cycled_mwh * dod_factor
        return soh * (1 - degradation_rate)

class Battery:
    """
    Manages battery operations including charging and discharging.
    """
    def __init__(self, capacity_mwh, charge_efficiency=0.9, discharge_efficiency=0.9, efficiency_adjuster=None, soh_calculator=None, **kwargs):
        self.validate_initial_conditions(capacity_mwh, kwargs.get('initial_soc', 0.5), kwargs.get('initial_soh', 1.0))
        
        self.capacity_mwh = capacity_mwh
        self.charge_efficiency = charge_efficiency
        self.discharge_efficiency = discharge_efficiency
        self.max_charge_rate_mw = kwargs.get('max_charge_rate_mw', capacity_mwh)
        self.max_discharge_rate_mw = kwargs.get('max_discharge_rate_mw', capacity_mwh)
        self.soc = kwargs.get('initial_soc', 0.5)
        self.soh = kwargs.get('initial_soh', 1.0)
        self.temperature_c = kwargs.get('temperature_c', 25)
        self.cycle_count = kwargs.get('starting_cycle_count', 0.0)
        self.energy_cycled_mwh = 0.0
        self.duration_hours = kwargs.get('duration_hours', 1.0)
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
        self.charge_efficiency, self.discharge_efficiency = self.efficiency_adjuster.adjust_efficiency(
            self.temperature_c, self.charge_efficiency, self.discharge_efficiency)
    
    def charge_or_discharge(self, energy_mwh, mode='charge'):
        self.adjust_efficiency_for_temperature()
        if mode == 'charge':
            energy_mwh = min(energy_mwh, self.max_charge_rate_mw * self.duration_hours)
            efficiency = self.charge_efficiency
        else: # 'discharge'
            energy_mwh = min(energy_mwh, self.max_discharge_rate_mw * self.duration_hours)
            efficiency = self.discharge_efficiency
        
        actual_energy_mwh = energy_mwh * efficiency
        if mode == 'charge':
            self.soc = min(self.soc + actual_energy_mwh / self.capacity_mwh, 1.0)
        else:
            self.soc = max(self.soc - actual_energy_mwh / self.capacity_mwh, 0.0)
        
        self.energy_cycled_mwh += energy_mwh
        dod = 1.0 - self.soc
        self.soh = self.soh_calculator.calculate_soh(self.soh, energy_mwh, dod)
        self.check_and_update_cycles()

    def check_and_update_cycles(self):
        if self.energy_cycled_mwh >= self.capacity_mwh:
            self.cycle_count += 1
            self.energy_cycled_mwh -= self.capacity_mwh
        self.last_cycle_soc = self.soc

    def charge(self, energy_mwh: float):
        self.charge_or_discharge(energy_mwh, mode='charge')

    def discharge(self, energy_mwh: float):
        self.charge_or_discharge(energy_mwh, mode='discharge')