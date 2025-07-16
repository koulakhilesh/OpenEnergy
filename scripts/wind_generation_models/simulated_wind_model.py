import datetime
import math
import random
import typing as t

from .interfaces import IWindData, IWindEnvelopeGenerator, IWindNoiseAdder


class SimulatedWindGenerationEnvelopeGenerator(IWindEnvelopeGenerator):
    """
    A simulated wind generation envelope generator.

    This generator creates realistic wind generation profiles based on
    mathematical models that simulate wind patterns throughout the day.
    """

    def __init__(self, capacity_kw: float = 1000.0, turbulence_factor: float = 0.3):
        """
        Initialize the wind generation envelope generator.

        Args:
            capacity_kw (float): Maximum wind generation capacity in kW.
            turbulence_factor (float): Factor controlling wind variability (0-1).
        """
        self.capacity_kw = capacity_kw
        self.turbulence_factor = turbulence_factor

    def generate(self, date: datetime.date) -> t.List[float]:
        """
        Generate wind generation envelopes for the given date.

        Wind patterns are modeled with:
        - Seasonal variations (stronger in winter)
        - Daily patterns (typically stronger in afternoon/evening)
        - Random turbulence for realistic variability

        Args:
            date (datetime.date): The date for which to generate wind generation envelopes.

        Returns:
            List[float]: A list of wind generation values for 24 hours.
        """
        generation = []

        # Seasonal factor
        month = date.month
        if month in [12, 1, 2]:  # Winter - stronger winds
            seasonal_factor = 1.3
        elif month in [6, 7, 8]:  # Summer - weaker winds
            seasonal_factor = 0.7
        else:  # Spring/Fall
            seasonal_factor = 1.0

        for hour in range(24):
            # Base daily pattern - wind typically stronger in afternoon/evening
            base_factor = 0.5 + 0.4 * math.sin((hour - 6) * math.pi / 12)
            base_factor = max(0.1, base_factor)  # Minimum generation

            # Add turbulence for realistic wind variability
            turbulence = 1 + self.turbulence_factor * (random.random() - 0.5)

            # Calculate generation
            hourly_generation = (
                self.capacity_kw * base_factor * seasonal_factor * turbulence
            )

            # Ensure within bounds
            hourly_generation = max(0, min(self.capacity_kw, hourly_generation))
            generation.append(hourly_generation)

        return generation


class SimulatedWindGenerationNoiseAdder(IWindNoiseAdder):
    """
    A simulated wind generation noise adder.

    Adds realistic noise to wind generation data to simulate
    measurement uncertainties and short-term wind fluctuations.
    """

    def __init__(self, noise_std: float = 0.05):
        """
        Initialize the noise adder.

        Args:
            noise_std (float): Standard deviation of the noise as a fraction of generation.
        """
        self.noise_std = noise_std

    def add(self, generations: t.List[float]) -> t.List[float]:
        """
        Adds noise to the given list of wind generation data.

        Args:
            generations (List[float]): The list of wind generation data to add noise to.

        Returns:
            List[float]: The list of wind generation data with added noise.
        """
        noisy_generations = []
        for generation in generations:
            # Add Gaussian noise proportional to generation level
            noise = random.gauss(0, self.noise_std * generation)
            noisy_generation = max(0, generation + noise)
            noisy_generations.append(noisy_generation)

        return noisy_generations


class SimulatedWindGenerationModel(IWindData):
    """
    A simulated wind generation model.

    This model generates realistic wind generation profiles using
    envelope generators and noise adders to simulate real-world
    wind farm behavior.
    """

    def __init__(
        self,
        envelope_generator: t.Optional[IWindEnvelopeGenerator] = None,
        noise_adder: t.Optional[IWindNoiseAdder] = None,
    ):
        """
        Initialize the simulated wind generation model.

        Args:
            envelope_generator (IWindEnvelopeGenerator): Generator for base wind patterns.
            noise_adder (IWindNoiseAdder): Adds realistic noise to generation data.
        """
        self.envelope_generator = (
            envelope_generator or SimulatedWindGenerationEnvelopeGenerator()
        )
        self.noise_adder = noise_adder or SimulatedWindGenerationNoiseAdder()

    def get_generation(
        self, date: datetime.date
    ) -> t.Tuple[t.List[float], t.List[float]]:
        """
        Get the wind generation data for a specific date.

        Args:
            date (datetime.date): The date for which to retrieve the wind generation data.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing two lists of floats.
                The first list represents the actual generated power in kW for each hour,
                and the second list represents the potential generation capacity in kW.
        """
        # Generate base envelope (potential generation)
        potential_generation = self.envelope_generator.generate(date)

        # Add noise to simulate actual generation (with curtailment, etc.)
        actual_generation = self.noise_adder.add(potential_generation)

        # Ensure actual generation doesn't exceed potential
        actual_generation = [
            min(actual, potential)
            for actual, potential in zip(actual_generation, potential_generation)
        ]

        return actual_generation, potential_generation
