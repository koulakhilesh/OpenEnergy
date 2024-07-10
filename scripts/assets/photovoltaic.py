from .interfaces import IPVSystem


class PVSystem(IPVSystem):
    def __init__(
        self,
        capacity_mw: float,
        initial_efficiency: float = 1.0,
        degradation_rate_per_year: float = 0.0001,
        duration_hours: float = 1.0,
    ):
        assert capacity_mw > 0, "Capacity must be positive"
        assert 0 < initial_efficiency <= 1, "Initial efficiency must be between 0 and 1"
        assert (
            0 <= degradation_rate_per_year < 1
        ), "Degradation rate must be between 0 and 1"
        assert duration_hours >= 0, "Duration hours must be positive"

        self.capacity_mw = capacity_mw
        self.initial_efficiency = initial_efficiency
        self.degradation_rate_per_year = degradation_rate_per_year
        self.duration_hours = duration_hours

    def calculate_current_efficiency(self, years: float) -> float:
        assert years >= 0, "Years must be non-negative"
        current_efficiency = max(
            0, self.initial_efficiency * (1 - self.degradation_rate_per_year) ** years
        )
        return current_efficiency

    def calculate_generation(self, normalized_irradiance: float, years: float) -> float:
        assert normalized_irradiance >= 0, "Normalized irradiance must be non-negative"
        current_efficiency = self.calculate_current_efficiency(years)
        generation_mw = (
            normalized_irradiance
            * self.capacity_mw
            * current_efficiency
            * self.duration_hours
        )
        return generation_mw
