class Battery:
    """
    Represents a battery with various properties and methods for charging, discharging, and monitoring its state.

    Attributes:
        capacity_mwh (float): The capacity of the battery in megawatt-hours (MWh).
        charge_efficiency (float): The efficiency of the battery during charging, ranging from 0.5 to 1.0.
        discharge_efficiency (float): The efficiency of the battery during discharging, ranging from 0.5 to 1.0.
        max_charge_rate_mw (float): The maximum charge rate of the battery in megawatts (MW).
        max_discharge_rate_mw (float): The maximum discharge rate of the battery in megawatts (MW).
        initial_soh (float): The initial state of health (SOH) of the battery, ranging from 0.0 to 1.0.
        initial_soc (float): The initial state of charge (SOC) of the battery, ranging from 0.0 to 1.0.
        starting_cycle_count (float): The initial cycle count of the battery.
        temperature_c (float): The temperature of the battery in Celsius.
        soc (float): The current state of charge (SOC) of the battery, ranging from 0.0 to 1.0.
        soh (float): The current state of health (SOH) of the battery, ranging from 0.0 to 1.0.
        cycle_count (float): The current cycle count of the battery.
        last_cycle_soc (float): The state of charge (SOC) at the start of the last cycle.
        energy_cycled_mwh (float): The total energy cycled by the battery in megawatt-hours (MWh).
    """

    def __init__(
        self,
        capacity_mwh: float,
        charge_efficiency: float = 0.9,
        discharge_efficiency: float = 0.9,
        max_charge_rate_mw=None,
        max_discharge_rate_mw=None,
        initial_soh: float = 1.0,
        initial_soc: float = 0.5,
        starting_cycle_count: float = 0.0,
        temperature_c: float = 25,
        duration_hours: float = 1.0,
    ):
        """
        Initializes a new instance of the Battery class.

        Args:
            capacity_mwh (float): The capacity of the battery in megawatt-hours (MWh).
            charge_efficiency (float, optional): The efficiency of the battery during charging, ranging from 0.5 to 1.0. Defaults to 0.9.
            discharge_efficiency (float, optional): The efficiency of the battery during discharging, ranging from 0.5 to 1.0. Defaults to 0.9.
            max_charge_rate_mw (float, optional): The maximum charge rate of the battery in megawatts (MW). Defaults to None.
            max_discharge_rate_mw (float, optional): The maximum discharge rate of the battery in megawatts (MW). Defaults to None.
            initial_soh (float, optional): The initial state of health (SOH) of the battery, ranging from 0.0 to 1.0. Defaults to 1.0.
            initial_soc (float, optional): The initial state of charge (SOC) of the battery, ranging from 0.0 to 1.0. Defaults to 0.5.
            starting_cycle_count (float, optional): The initial cycle count of the battery. Defaults to 0.0.
            temperature_c (float, optional): The temperature of the battery in Celsius. Defaults to 25.
        """

        if capacity_mwh <= 0:
            raise ValueError("Capacity must be greater than 0")
        if not (0 <= initial_soc <= 1):
            raise ValueError("Initial SOC must be between 0 and 1")
        if initial_soh < 0 or initial_soh > 1:
            raise ValueError("Initial SOH must be between 0 and 1")

        self.capacity_mwh = capacity_mwh
        self.charge_efficiency = charge_efficiency
        self.discharge_efficiency = discharge_efficiency
        self.max_charge_rate_mw = (
            max_charge_rate_mw if max_charge_rate_mw else capacity_mwh
        )
        self.max_discharge_rate_mw = (
            max_discharge_rate_mw if max_discharge_rate_mw else capacity_mwh
        )
        self.soc = initial_soc
        self.soh = initial_soh
        self.temperature_c = temperature_c
        self.cycle_count = starting_cycle_count
        self.last_cycle_soc = initial_soc
        self.energy_cycled_mwh = 0.0
        self.duration_hours = duration_hours

    def adjust_efficiency_for_temperature(self):
        temp_effect = abs(self.temperature_c - 25) * 0.01
        self.charge_efficiency -= temp_effect
        self.discharge_efficiency -= temp_effect
        self.charge_efficiency = max(0.5, min(self.charge_efficiency, 1.0))
        self.discharge_efficiency = max(0.5, min(self.discharge_efficiency, 1.0))

    def charge(self, energy_mwh: float):
        self.adjust_efficiency_for_temperature()
        charge_energy_mwh = min(
            energy_mwh, self.max_charge_rate_mw * self.duration_hours
        )
        actual_charge_energy_mwh = charge_energy_mwh * self.charge_efficiency
        self.soc = min(self.soc + actual_charge_energy_mwh / self.capacity_mwh, 1.0)
        self.energy_cycled_mwh += charge_energy_mwh
        dod = 1.0 - self.soc
        self.update_soh(charge_energy_mwh, dod)
        self.check_and_update_cycles()

    def discharge(self, energy_mwh: float):
        self.adjust_efficiency_for_temperature()
        discharge_energy_mwh = min(
            energy_mwh, self.max_discharge_rate_mw * self.duration_hours
        )
        actual_discharge_energy_mwh = discharge_energy_mwh * self.discharge_efficiency
        self.soc = max(self.soc - actual_discharge_energy_mwh / self.capacity_mwh, 0.0)
        self.energy_cycled_mwh += discharge_energy_mwh
        dod = 1.0 - self.soc
        self.update_soh(discharge_energy_mwh, dod)
        self.check_and_update_cycles()

    def check_and_update_cycles(self):
        if self.energy_cycled_mwh >= self.capacity_mwh:
            self.cycle_count += 1
            self.energy_cycled_mwh -= self.capacity_mwh
        self.last_cycle_soc = self.soc

    def get_soc(self) -> float:
        return self.soc

    def get_soh(self) -> float:
        return self.soh

    def update_soh(self, energy_cycled_mwh: float, dod: float):
        base_degradation = 0.000005
        dod_factor = 2 if dod > 0.5 else 1
        degradation_rate = base_degradation * energy_cycled_mwh * dod_factor
        self.soh *= 1 - degradation_rate
