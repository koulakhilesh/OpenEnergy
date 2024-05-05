import datetime
import math
import random
import typing as t

from .interfaces import IPriceData, IPriceEnvelopeGenerator, IPriceNoiseAdder


class SimulatedPriceEnvelopeGenerator(IPriceEnvelopeGenerator):
    def __init__(
        self,
        num_intervals: int = 24,
        min_price: float = 0.0,
        max_price: float = 200.0,
        peak_start: float = 16.0,
        peak_end: float = 32.0,
    ):
        self.num_intervals = num_intervals
        self.min_price = min_price
        self.max_price = max_price
        self.peak_start = peak_start
        self.peak_end = peak_end

    def generate(self, date: datetime.date) -> t.List[float]:
        random.seed(date.toordinal())
        prices = []
        for i in range(self.num_intervals):
            x = (math.pi * 2) * (i / self.num_intervals)

            if self.peak_start <= i < self.peak_end:
                sine_value = (math.sin(x - math.pi / 2) + 1) / 2
                price = self.min_price + (self.max_price - self.min_price) * sine_value
            else:
                off_peak_amplitude = (self.max_price - self.min_price) / 4
                sine_value = (math.sin(x * 2 - math.pi / 2) + 1) / 2
                price = self.min_price + off_peak_amplitude * sine_value

            random_adjustment = (
                random.uniform(-1, 1) * (self.max_price - self.min_price) / 20
            )
            price += random_adjustment
            price = float(max(self.min_price, min(price, self.max_price)))

            prices.append(price)

        return prices


class SimulatedPriceNoiseAdder(IPriceNoiseAdder):
    def __init__(
        self,
        noise_level: float = 5.0,
        spike_chance: float = 0.05,
        spike_multiplier: float = 1.5,
    ):
        self.noise_level = noise_level
        self.spike_chance = spike_chance
        self.spike_multiplier = spike_multiplier

    def add(self, prices: t.List[float]) -> t.List[float]:
        noisy_prices = []
        for price in prices:
            noise = random.uniform(-self.noise_level, self.noise_level)
            new_price = price + noise

            if random.random() < self.spike_chance:
                new_price *= self.spike_multiplier

            new_price = float(max(0, new_price))
            noisy_prices.append(new_price)

        return noisy_prices


class SimulatedPriceModel(IPriceData):
    def __init__(
        self, envelope_generator: IPriceEnvelopeGenerator, noise_adder: IPriceNoiseAdder
    ):
        self.envelope_generator = envelope_generator
        self.noise_adder = noise_adder

    def get_prices(self, date: datetime.date) -> t.Tuple[t.List[float], t.List[float]]:
        prices = self.envelope_generator.generate(date=date)
        prices_with_noise_and_spikes = self.noise_adder.add(prices)
        return prices, prices_with_noise_and_spikes
