import datetime
import math
import random
import typing as t

from .interfaces import IPVData, IPVEnvelopeGenerator, IPVNoiseAdder


class SimulatedPVGenerationEnvelopeGenerator(IPVEnvelopeGenerator):
    """
    A class that generates a simulated PV generation envelope based on a sine wave.

    Attributes:
        num_intervals (int): The number of intervals in the generation envelope.
        min_generation (float): The minimum generation value in the envelope.
        max_generation (float): The maximum generation value in the envelope.
        peak_sun_hours_start (float): The start index of the peak sun hours interval.
        peak_sun_hours_end (float): The end index of the peak sun hours interval.
    """

    def __init__(
        self,
        num_intervals: int = 24,
        min_generation: float = 0.0,
        max_generation: float = 100.0,
        peak_sun_hours_start: float = 8.0,
        peak_sun_hours_end: float = 16.0,
    ):
        self.num_intervals = num_intervals
        self.min_generation = min_generation
        self.max_generation = max_generation
        self.peak_sun_hours_start = peak_sun_hours_start
        self.peak_sun_hours_end = peak_sun_hours_end

    def generate(self, date: datetime.date) -> t.List[float]:
        """
        Generates a simulated PV generation envelope for the given date.

        Args:
            date (datetime.date): The date for which to generate the PV generation envelope.

        Returns:
            List[float]: A list of generation values representing the PV generation envelope.
        """
        random.seed(date.toordinal())
        generations = []
        for i in range(self.num_intervals):
            x = (math.pi * 2) * (i / self.num_intervals)

            if self.peak_sun_hours_start <= i < self.peak_sun_hours_end:
                sine_value = (math.sin(x) + 1) / 2
                generation = (
                    self.min_generation
                    + (self.max_generation - self.min_generation) * sine_value
                )
            else:
                off_peak_amplitude = (self.max_generation - self.min_generation) / 4
                sine_value = (math.sin(x * 2) + 1) / 2
                generation = self.min_generation + off_peak_amplitude * sine_value

            random_adjustment = (
                random.uniform(-1, 1) * (self.max_generation - self.min_generation) / 20
            )
            generation += random_adjustment
            generation = float(
                max(self.min_generation, min(generation, self.max_generation))
            )

            generations.append(generation)

        return generations


class SimulatedPVGenerationNoiseAdder(IPVNoiseAdder):
    """
    A class that adds simulated noise to a list of PV generation values.

    Attributes:
        noise_level (float): The maximum amount of noise to add to each generation value.
        spike_chance (float): The probability of a generation spike occurring.
        spike_multiplier (float): The multiplier applied to generation values when a spike occurs.
    """

    def __init__(
        self,
        noise_level: float = 10.0,
        spike_chance: float = 0.02,
        spike_multiplier: float = 2.0,
    ):
        self.noise_level = noise_level
        self.spike_chance = spike_chance
        self.spike_multiplier = spike_multiplier

    def add(self, generations: t.List[float]) -> t.List[float]:
        """
        Adds simulated noise to a list of PV generation values.

        Args:
            generations (List[float]): The list of PV generation values to add noise to.

        Returns:
            List[float]: The list of PV generation values with simulated noise added.
        """
        noisy_generations = []
        for generation in generations:
            noise = random.uniform(-self.noise_level, self.noise_level)
            new_generation = generation + noise

            if random.random() < self.spike_chance:
                new_generation *= self.spike_multiplier

            new_generation = float(max(0, new_generation))
            noisy_generations.append(new_generation)

        return noisy_generations


class SimulatedPVGenerationModel(IPVData):
    """
    A class representing a simulated PV generation model.

    This class generates simulated PV generation data based on an envelope generator
    and adds noise to the generated generations using a noise adder.

    Attributes:
        envelope_generator (IPVEnvelopeGenerator): An instance of the envelope generator.
        noise_adder (IPVNoiseAdder): An instance of the noise adder.

    Methods:
        get_generations(date: datetime.date) -> Tuple[List[float], List[float]]:
            Generates simulated PV generations for the given date and returns the generations
            with and without noise and spikes.

    """

    def __init__(
        self, envelope_generator: IPVEnvelopeGenerator, noise_adder: IPVNoiseAdder
    ):
        self.envelope_generator = envelope_generator
        self.noise_adder = noise_adder

    def get_generations(
        self, date: datetime.date
    ) -> t.Tuple[t.List[float], t.List[float]]:
        """
        Generates simulated PV generations for the given date.

        Args:
            date (datetime.date): The date for which PV generations need to be generated.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing two lists of PV generations.
            The first list represents the generations without noise and spikes,
            and the second list represents the generations with noise and spikes.

        """
        generations = self.envelope_generator.generate(date=date)
        generations_with_noise_and_spikes = self.noise_adder.add(generations)
        return generations, generations_with_noise_and_spikes
