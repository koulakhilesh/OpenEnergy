class Battery:
    def __init__(
        self,
        capacity_mwh: float,
        charge_efficiency: float = 0.9,
        discharge_efficiency: float = 0.9,
        max_charge_rate=None,
        max_discharge_rate=None,
        initial_soh: float = 1.0,
        initial_soc: float = 0.0,
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
        self.max_charge_rate = max_charge_rate if max_charge_rate else capacity_mwh
        self.max_discharge_rate = (
            max_discharge_rate if max_discharge_rate else capacity_mwh
        )

    def charge(self, mwh: float, duration_hours=0.5):
        charge_amount = min(mwh, self.max_charge_rate * duration_hours)
        actual_charge = charge_amount * self.charge_efficiency
        self.soc = min(self.soc + actual_charge / self.capacity_mwh, 1.0)
        energy_cycled = charge_amount * duration_hours
        dod = self.soc
        self.update_soh(energy_cycled, dod)

    def discharge(self, mwh: float, duration_hours=0.5):
        discharge_amount = min(mwh, self.max_discharge_rate * duration_hours)
        actual_discharge = discharge_amount * self.discharge_efficiency
        self.soc = max(self.soc - actual_discharge / self.capacity_mwh, 0.0)
        energy_cycled = discharge_amount * duration_hours
        dod = self.soc
        self.update_soh(energy_cycled, dod)

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
        degradation_rate = self.calculate_degradation_rate(energy_cycled_mwh, dod)
        self.soh *= 1 - degradation_rate

    def calculate_degradation_rate(self, energy_cycled_mwh: float, dod: float) -> float:
        """
        Calculate the degradation rate based on the energy cycled and depth of discharge.
        """
        base_degradation = 0.00005  # Base degradation rate per MWh cycled
        dod_factor = 2 if dod > 0.5 else 1  # Higher degradation if DoD is more than 50%
        return base_degradation * energy_cycled_mwh * dod_factor
