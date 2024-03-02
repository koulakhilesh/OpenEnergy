import math
import random
import datetime
import pandas as pd
import pytz
import typing as t
from abc import ABC, abstractmethod


class IPriceData(ABC):
    """Interface for retrieving price data."""

    @abstractmethod
    def get_prices(self, date: datetime.date) -> t.Tuple[t.List[float], t.List[float]]:
        """Get the prices for a given date.

        Args:
            date (datetime.date): The date for which to retrieve the prices.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing two lists of floats representing the prices.
        """
        pass


class IDataProvider:
    """Interface for data providers."""

    def get_data(self) -> pd.DataFrame:
        """Get data from the provider."""
        pass


class CSVDataProvider(IDataProvider):
    """
    A data provider that reads data from a CSV file.

    Args:
        csv_file_path (str): The path to the CSV file.

    Returns:
        pd.DataFrame: The data read from the CSV file.
    """

    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path

    def get_data(self) -> pd.DataFrame:
        return pd.read_csv(
            self.csv_file_path,
            parse_dates=["utc_timestamp"],
            infer_datetime_format=True,
        )


class PriceSimulator(IPriceData):
    """
    A class that simulates price data for a given date.

    Attributes:
        None

    Methods:
        get_prices: Returns the simulated prices for a given date.
        price_envelope: Generates the price envelope for a given date.
        add_noise_and_spikes: Adds noise and spikes to the prices.

    """

    def get_prices(self, date: datetime.date) -> t.Tuple[t.List[float], t.List[float]]:
        """
        Returns the simulated prices for a given date.

        Args:
            date (datetime.date): The date for which to generate prices.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing the original prices and the prices with noise and spikes.

        """

        prices = self.price_envelope(date=date)
        prices_with_noise_and_spikes = self.add_noise_and_spikes(prices)
        return prices, prices_with_noise_and_spikes

    @staticmethod
    def price_envelope(
        num_intervals=24,
        min_price=0,
        max_price=200,
        peak_start=16,
        peak_end=32,
        date=datetime.date.today(),
    ) -> t.List[float]:
        """
        Generates the price envelope for a given date.

        Args:
            num_intervals (int): The number of intervals in a day.
            min_price (float): The minimum price.
            max_price (float): The maximum price.
            peak_start (int): The start hour of the peak period.
            peak_end (int): The end hour of the peak period.
            date (datetime.date): The date for which to generate the price envelope.

        Returns:
            List[float]: The price envelope for the given date.

        """

        random.seed(date.toordinal())

        prices = []
        for i in range(num_intervals):
            x = (math.pi * 2) * (i / num_intervals)

            if peak_start <= i < peak_end:
                sine_value = (math.sin(x - math.pi / 2) + 1) / 2
                price = min_price + (max_price - min_price) * sine_value
            else:
                off_peak_amplitude = (max_price - min_price) / 4
                sine_value = (math.sin(x * 2 - math.pi / 2) + 1) / 2
                price = min_price + off_peak_amplitude * sine_value

            random_adjustment = random.uniform(-1, 1) * (max_price - min_price) / 20
            price += random_adjustment
            price = max(min_price, min(price, max_price))

            prices.append(price)

        return prices

    @staticmethod
    def add_noise_and_spikes(
        prices: t.List[float],
        noise_level=5,
        spike_chance=0.05,
        spike_multiplier=1.5,
    ) -> t.List[float]:
        """
        Adds noise and spikes to the prices.

        Args:
            prices (List[float]): The original prices.
            noise_level (float): The level of noise to add.
            spike_chance (float): The chance of adding a spike to a price.
            spike_multiplier (float): The multiplier for the spike.

        Returns:
            List[float]: The prices with noise and spikes.

        """

        noisy_prices = []
        for price in prices:
            noise = random.uniform(-noise_level, noise_level)
            new_price = price + noise

            if random.random() < spike_chance:
                new_price *= spike_multiplier

            new_price = max(0, new_price)
            noisy_prices.append(new_price)

        return noisy_prices


class PriceModel(IPriceData):
    """
    Represents a model for retrieving and analyzing price data.

    Args:
        data_provider (IDataProvider): The data provider used to fetch the price data.

    Attributes:
        data_provider (IDataProvider): The data provider used to fetch the price data.
        data (pandas.DataFrame): The fetched price data.

    """

    def __init__(self, data_provider: IDataProvider):
        self.data_provider = data_provider
        self.data = self.data_provider.get_data()

    def get_prices(self, date: datetime.date) -> t.Tuple[t.List[float], t.List[float]]:
        """
        Retrieves the average prices for the last week and the prices for the specified date.

        Args:
            date (datetime.date): The date for which to retrieve the prices.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing the average prices for the last week
            and the prices for the specified date.

        """
        current_date = datetime.datetime.combine(date, datetime.time.min).replace(
            tzinfo=pytz.utc
        )
        week_prior = current_date - datetime.timedelta(days=7)

        last_week_data = self.data[
            (self.data["utc_timestamp"] >= week_prior)
            & (self.data["utc_timestamp"] < current_date)
        ]

        average_prices_last_week = (
            last_week_data.groupby(last_week_data["utc_timestamp"].dt.hour)[
                "GB_GBN_price_day_ahead"
            ]
            .mean()
            .tolist()
        )

        current_date_data = self.data[
            self.data["utc_timestamp"].dt.date == current_date.date()
        ]

        prices_current_date = current_date_data.set_index(
            current_date_data["utc_timestamp"].dt.hour
        )["GB_GBN_price_day_ahead"].tolist()

        return average_prices_last_week, prices_current_date


if __name__ == "__main__":
    data_provider = CSVDataProvider(
        "data\\time_series\\time_series_60min_singleindex_filtered.csv"
    )
    price_model = PriceModel(data_provider)
    date_provided = datetime.date(2018, 1, 1)

    average_prices, prices_for_day = price_model.get_prices(date_provided)
    print("Average prices last week per hour:", average_prices)
    print("Prices for the current date per hour:", prices_for_day)

    price_simulator = PriceSimulator()
    simulated_prices, simulated_prices_with_noise = price_simulator.get_prices(
        date_provided
    )
    print(f"Simulated Prices on {date_provided}: {simulated_prices}")
    print(
        f"Simulated Prices with Noise and Spikes on {date_provided}: {simulated_prices_with_noise}"
    )
