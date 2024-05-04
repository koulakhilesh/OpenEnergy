import datetime
import math
import random
import typing as t
from abc import ABC, abstractmethod

import pandas as pd
import pytz


class IPriceData(ABC):
    @abstractmethod
    def get_prices(self, date: datetime.date) -> t.Tuple[t.List[float], t.List[float]]:
        pass


class IPriceEnvelopeGenerator(ABC):
    @abstractmethod
    def generate(self, date: datetime.date) -> t.List[float]:
        pass


class IPriceNoiseAdder(ABC):
    @abstractmethod
    def add(self, prices: t.List[float]) -> t.List[float]:
        pass


class IDataProvider:
    def get_data(self):
        pass


class SimulatedPriceEnvelopeGenerator(IPriceEnvelopeGenerator):
    def __init__(
        self, num_intervals=24, min_price=0, max_price=200, peak_start=16, peak_end=32
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
    def __init__(self, noise_level=5, spike_chance=0.05, spike_multiplier=1.5):
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


class CSVDataProvider(IDataProvider):
    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path

    def get_data(self) -> pd.DataFrame:
        return pd.read_csv(
            self.csv_file_path,
            parse_dates=["utc_timestamp"],
            infer_datetime_format=True,
        )


class HistoricalAveragePriceModel(IPriceData):
    DAYS_IN_WEEK = 7

    def __init__(self, data_provider: IDataProvider):
        self.data_provider = data_provider
        self.data = self.data_provider.get_data()

    def get_prices(self, date: datetime.date) -> t.Tuple[t.List[float], t.List[float]]:
        current_date = self._get_current_date(date)
        week_prior = self._get_week_prior(current_date)

        last_week_data = self._get_last_week_data(current_date, week_prior)
        average_prices_last_week = self._get_average_prices_last_week(last_week_data)

        current_date_data = self._get_current_date_data(current_date)
        prices_current_date = self._get_prices_current_date(current_date_data)

        return average_prices_last_week, prices_current_date

    def _get_current_date(self, date: datetime.date) -> datetime.datetime:
        return datetime.datetime.combine(date, datetime.time.min).replace(
            tzinfo=pytz.utc
        )

    def _get_week_prior(self, current_date: datetime.datetime) -> datetime.datetime:
        return current_date - datetime.timedelta(days=self.DAYS_IN_WEEK)

    def _get_last_week_data(
        self, current_date: datetime.datetime, week_prior: datetime.datetime
    ) -> pd.DataFrame:
        return self.data[
            (self.data["utc_timestamp"] >= week_prior)
            & (self.data["utc_timestamp"] < current_date)
        ]

    def _get_average_prices_last_week(
        self, last_week_data: pd.DataFrame
    ) -> t.List[float]:
        return (
            last_week_data.groupby(last_week_data["utc_timestamp"].dt.hour)[
                "GB_GBN_price_day_ahead"
            ]
            .mean()
            .tolist()
        )

    def _get_current_date_data(self, current_date: datetime.datetime) -> pd.DataFrame:
        return self.data[self.data["utc_timestamp"].dt.date == current_date.date()]

    def _get_prices_current_date(
        self, current_date_data: pd.DataFrame
    ) -> t.List[float]:
        return current_date_data.set_index(current_date_data["utc_timestamp"].dt.hour)[
            "GB_GBN_price_day_ahead"
        ].tolist()
