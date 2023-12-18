class Battery:
    def __init__(
        self,
        capacity_mwh: float,
        charge_efficiency: float = 0.9,
        discharge_efficiency: float = 0.9,
        max_charge_rate_mw=None,
        max_discharge_rate_mw=None,
        initial_soh: float = 1.0,
        initial_soc: float = 0.0,
        starting_cycle_count: float = 0.0
    ):
        if capacity_mwh <= 0:
            raise ValueError("Capacity must be greater than 0")
        if not (0 <= initial_soc <= 1):
            raise ValueError("Initial SOC must be between 0 and 1")
        if initial_soh < 0 or initial_soh > 1:
            raise ValueError("Initial SOH must be between 0 and 1")

        self.capacity_mwh = capacity_mwh
        self.charge_efficiency = charge_efficiency
        self.discharge_efficiency = discharge_efficiency
        self.soc = initial_soc  # Initial state of charge as a fraction (0 to 1)
        self.soh = initial_soh
        self.max_charge_rate_mw = max_charge_rate_mw if max_charge_rate_mw else capacity_mwh
        self.max_discharge_rate_mw = (
            max_discharge_rate_mw if max_discharge_rate_mw else capacity_mwh
        )
        self.cycle_count = starting_cycle_count
        self.last_cycle_soc = initial_soc  # Keep track of SOC at the last cycle
        self.energy_cycled_mwh = 0.0  # Track total energy cycled

    def charge(self, energy_mwh: float, duration_hours=0.5):
        # Calculate the actual charge based on energy and efficiency
        charge_energy_mwh = min(energy_mwh, self.max_charge_rate_mw * duration_hours)
        actual_charge_energy_mwh = charge_energy_mwh * self.charge_efficiency

        # Update SOC and energy_cycled
        self.soc = min(self.soc + actual_charge_energy_mwh / self.capacity_mwh, 1.0)
        self.energy_cycled_mwh += charge_energy_mwh

        # Calculate DoD and update SOH and cycle count
        dod = 1.0 - self.soc
        self.update_soh(charge_energy_mwh, dod)
        self.check_and_update_cycles()

    def discharge(self, energy_mwh: float, duration_hours=0.5):
        # Calculate the actual discharge based on energy and efficiency
        discharge_energy_mwh = min(energy_mwh, self.max_discharge_rate_mw * duration_hours)
        actual_discharge_energy_mwh = discharge_energy_mwh * self.discharge_efficiency

        # Update SOC and energy_cycled
        self.soc = max(self.soc - actual_discharge_energy_mwh / self.capacity_mwh, 0.0)
        self.energy_cycled_mwh += discharge_energy_mwh

        # Calculate DoD and update SOH and cycle count
        dod = 1.0 - self.soc
        self.update_soh(discharge_energy_mwh, dod)
        self.check_and_update_cycles()

    def check_and_update_cycles(self):
        # Check for significant cycles based on energy_cycled_mwh
        # Update cycle_count accordingly
        if self.energy_cycled_mwh >= self.capacity_mwh:
            self.cycle_count += 1
            self.energy_cycled_mwh -= self.capacity_mwh
        self.last_cycle_soc = self.soc

    def get_soc(self) -> float:
        """Return the current state of charge."""
        return self.soc

    def get_soh(self) -> float:
        """Return the current state of health."""
        return self.soh

    def update_soh(self, energy_cycled_mwh: float, dod: float):
        """
        Update the State of Health (SOH) of the battery.
        """
        base_degradation = 0.00005  # Base degradation rate per MWh cycled
        dod_factor = 2 if dod > 0.5 else 1  # Higher degradation if DoD is more than 50%
        degradation_rate = base_degradation * energy_cycled_mwh * dod_factor
        self.soh *= 1 - degradation_rate

    def calculate_degradation_rate(self, energy_cycled_mwh: float, dod: float) -> float:
        """
        Calculate the degradation rate based on the energy cycled and depth of discharge.
        """
        base_degradation = 0.00005  # Base degradation rate per MWh cycled
        dod_factor = 2 if dod > 0.5 else 1  # Higher degradation if DoD is more than 50%
        return base_degradation * energy_cycled_mwh * dod_factor
