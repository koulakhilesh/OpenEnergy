import datetime
import typing as t
from abc import ABC, abstractmethod

import pandas as pd


class IWindData(ABC):
    """Interface for retrieving wind generation data."""

    @abstractmethod
    def get_generation(
        self, date: datetime.date
    ) -> t.Tuple[t.List[float], t.List[float]]:
        """Get the wind generation data for a specific date.

        Args:
            date (datetime.date): The date for which to retrieve the wind generation data.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing two lists of floats.
                The first list represents the generated power in kW for each hour of the day,
                and the second list represents the estimated potential generation in kW.
        """
        pass


class IWindEnvelopeGenerator(ABC):
    """
    Interface for generating wind generation envelopes.
    """

    @abstractmethod
    def generate(self, date: datetime.date) -> t.List[float]:
        """
        Generate wind generation envelopes for the given date.

        Args:
            date (datetime.date): The date for which to generate wind generation envelopes.

        Returns:
            List[float]: A list of wind generation envelopes.
        """
        pass


class IWindNoiseAdder(ABC):
    """
    Interface for adding noise to a list of wind generation data.
    """

    @abstractmethod
    def add(self, generations: t.List[float]) -> t.List[float]:
        """
        Adds noise to the given list of wind generation data.

        Args:
            generations (List[float]): The list of wind generation data to add noise to.

        Returns:
            List[float]: The list of wind generation data with added noise.
        """
        pass


class IWindDataHelper(ABC):
    """Interface for a wind data helper."""

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
    def get_prior_date(
        self, current_date: datetime.datetime, delta_days: int
    ) -> datetime.datetime:
        """Get the date a certain number of days before the current date.

        Args:
            current_date (datetime.datetime): The current date and time.
            delta_days (int): The number of days before the current date to retrieve.

        Returns:
            datetime.datetime: The date before the current date by the specified number of days.
        """
        pass

    @abstractmethod
    def get_prior_data(
        self,
        current_date: datetime.datetime,
        prior_date: datetime.datetime,
        wind_data: IWindData,
    ) -> pd.DataFrame:
        """Get the wind generation data for the period between two dates.

        Args:
            current_date (datetime.datetime): The current date and time.
            prior_date (datetime.datetime): The prior date and time.
            wind_data (IWindData): The wind data interface for retrieving wind generation data.

        Returns:
            pd.DataFrame: A DataFrame containing the wind generation data for the specified period.
        """
        pass

    @abstractmethod
    def get_prior_data_as_list(
        self,
        current_date: datetime.datetime,
        prior_date: datetime.datetime,
        wind_data: IWindData,
    ) -> t.List[float]:
        """Get the wind generation data for the period between two dates as a list.

        Args:
            current_date (datetime.datetime): The current date and time.
            prior_date (datetime.datetime): The prior date and time.
            wind_data (IWindData): The wind data interface for retrieving wind generation data.

        Returns:
            List[float]: A list containing the wind generation data for the specified period.
        """
        pass

    @abstractmethod
    def get_seasonal_trend(
        self, date: datetime.date, base_generation: t.List[float]
    ) -> t.List[float]:
        """Apply seasonal trends to base wind generation data.

        Args:
            date (datetime.date): The date for seasonal calculations.
            base_generation (List[float]): Base wind generation values.

        Returns:
            List[float]: Wind generation data with seasonal adjustments.
        """
        pass

    @abstractmethod
    def get_wind_speed_factor(self, hour: int) -> float:
        """Get wind speed factor for a specific hour of the day.

        Args:
            hour (int): Hour of the day (0-23).

        Returns:
            float: Wind speed factor for the given hour.
        """
        pass
