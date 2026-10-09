import datetime
import typing as t
from abc import ABC, abstractmethod

import pandas as pd


class IPVData(ABC):
    """Interface for retrieving photovoltaic (PV) generation data."""

    @abstractmethod
    def get_generation(
        self, date: datetime.date
    ) -> t.Tuple[t.List[float], t.List[float]]:
        """Get the PV generation data for a specific date.

        Args:
            date (datetime.date): The date for which to retrieve the PV generation data.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing two lists of floats.
                The first list represents the generated power in kW for each hour of the day,
                and the second list represents the estimated potential generation in kW.
        """
        pass


class IPVEnvelopeGenerator(ABC):
    """
    Interface for generating PV generation envelopes.
    """

    @abstractmethod
    def generate(self, date: datetime.date) -> t.List[float]:
        """
        Generate PV generation envelopes for the given date.

        Args:
            date (datetime.date): The date for which to generate PV generation envelopes.

        Returns:
            List[float]: A list of PV generation envelopes.
        """
        pass


class IPVNoiseAdder(ABC):
    """
    Interface for adding noise to a list of PV generation data.
    """

    @abstractmethod
    def add(self, generations: t.List[float]) -> t.List[float]:
        """
        Adds noise to the given list of PV generation data.

        Args:
            generations (List[float]): The list of PV generation data to add noise to.

        Returns:
            List[float]: The list of PV generation data with added noise.
        """
        pass


class IPVDataHelper(ABC):
    """Interface for a PV data helper."""

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
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Get the PV generation data for the days prior to the current date.

        Args:
            current_date (datetime.datetime): The current date and time.
            prior_date (datetime.datetime): The prior date to compare.
            data (pd.DataFrame): The dataset containing PV generation data.

        Returns:
            pd.DataFrame: The filtered dataset containing data for the days prior to the current date.
        """
        pass

    @abstractmethod
    def get_current_date_data(
        self, current_date: datetime.datetime, data: pd.DataFrame
    ) -> pd.DataFrame:
        """Get the PV generation data for the current date.

        Args:
            current_date (datetime.datetime): The current date and time.
            data (pd.DataFrame): The dataset containing PV generation data.

        Returns:
            pd.DataFrame: The filtered dataset for the current date.
        """
        pass

    @abstractmethod
    def get_generation_current_date(
        self, current_date_data: pd.DataFrame, column_name: str
    ) -> t.List[float]:
        """Get the PV generation data for the current date.

        Args:
            current_date_data (pd.DataFrame): The dataset for the current date.
            column_name (str): The name of the column containing the PV generation data.

        Returns:
            List[float]: The PV generation data for the current date.
        """
        pass
