import datetime
import typing as t
from abc import ABC, abstractmethod

import pandas as pd


class IPriceData(ABC):
    """Interface for retrieving price data."""

    @abstractmethod
    def get_prices(self, date: datetime.date) -> t.Tuple[t.List[float], t.List[float]]:
        """Get the prices for a specific date.

        Args:
            date (datetime.date): The date for which to retrieve the prices.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing two lists of floats.
                The first list represents the buy prices, and the second list represents
                the sell prices.
        """
        pass


class IPriceEnvelopeGenerator(ABC):
    """
    Interface for generating price envelopes.
    """

    @abstractmethod
    def generate(self, date: datetime.date) -> t.List[float]:
        """
        Generate price envelopes for the given date.

        Args:
            date (datetime.date): The date for which to generate price envelopes.

        Returns:
            List[float]: A list of price envelopes.
        """
        pass


class IPriceNoiseAdder(ABC):
    """
    Interface for adding noise to a list of prices.
    """

    @abstractmethod
    def add(self, prices: t.List[float]) -> t.List[float]:
        """
        Adds noise to the given list of prices.

        Args:
            prices (List[float]): The list of prices to add noise to.

        Returns:
            List[float]: The list of prices with added noise.
        """
        pass


class IPriceDataHelper(ABC):
    """Interface for a price data helper."""

    @abstractmethod
    def get_current_date(self, date: datetime.date) -> datetime.datetime:
        """Get the current date and time.

        Args:
            date (datetime.date): The current date.

        Returns:
            datetime.datetime: The current date and time.
        """
        pass

    @abstractmethod
    def get_week_prior(
        self, current_date: datetime.datetime, delta_days: int
    ) -> datetime.datetime:
        """Get the date and time of the week prior to the given date.

        Args:
            current_date (datetime.datetime): The current date and time.
            delta_days (int): The number of days to go back.

        Returns:
            datetime.datetime: The date and time of the week prior.
        """
        pass

    @abstractmethod
    def get_last_week_data(
        self,
        current_date: datetime.datetime,
        week_prior: datetime.datetime,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Get the data for the last week.

        Args:
            current_date (datetime.datetime): The current date and time.
            week_prior (datetime.datetime): The date and time of the week prior.
            data (pd.DataFrame): The data to filter.

        Returns:
            pd.DataFrame: The filtered data for the last week.
        """
        pass

    @abstractmethod
    def get_current_date_data(
        self, current_date: datetime.datetime, data: pd.DataFrame
    ) -> pd.DataFrame:
        """Get the data for the current date.

        Args:
            current_date (datetime.datetime): The current date and time.
            data (pd.DataFrame): The data to filter.

        Returns:
            pd.DataFrame: The filtered data for the current date.
        """
        pass

    @abstractmethod
    def get_prices_current_date(
        self, current_date_data: pd.DataFrame, column_name: str
    ) -> t.List[float]:
        """Get the prices for the current date.

        Args:
            current_date_data (pd.DataFrame): The data for the current date.
            column_name (str): The name of the column containing the prices.

        Returns:
            List[float]: The prices for the current date.
        """
        pass
