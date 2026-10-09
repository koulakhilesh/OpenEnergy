import datetime
import typing as t

import pandas as pd
import pytz  # type: ignore

from .interfaces import IPVDataHelper


class PVDataHelper(IPVDataHelper):
    """Helper class for manipulating PV generation data."""

    def get_current_date(self, date: datetime.date) -> datetime.datetime:
        """Get the current date as a datetime object with time set to midnight in UTC.

        Args:
            date (datetime.date): The current date.

        Returns:
            datetime.datetime: The current date as a datetime object in UTC.
        """
        return datetime.datetime.combine(date, datetime.time.min).replace(
            tzinfo=pytz.utc
        )

    def get_prior_date(
        self, current_date: datetime.datetime, delta_days: int
    ) -> datetime.datetime:
        """Get the date a certain number of days before the current date.

        Args:
            current_date (datetime.datetime): The current date.
            delta_days (int): The number of days before the current date to retrieve.

        Returns:
            datetime.datetime: The date before the current date by the specified number of days.
        """
        return current_date - datetime.timedelta(days=delta_days)

    def get_prior_data(
        self,
        current_date: datetime.datetime,
        prior_date: datetime.datetime,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Get the PV generation data for the days prior to the current date.

        Args:
            current_date (datetime.datetime): The current date.
            prior_date (datetime.datetime): The prior date to compare.
            data (pd.DataFrame): The dataset containing PV generation data.

        Returns:
            pd.DataFrame: The filtered dataset containing data for the days prior to the current date.
        """
        return data[(data.index >= prior_date) & (data.index < current_date)]

    def get_current_date_data(
        self, current_date: datetime.datetime, data: pd.DataFrame
    ) -> pd.DataFrame:
        """Get the PV generation data for the current date.

        Args:
            current_date (datetime.datetime): The current date.
            data (pd.DataFrame): The dataset containing PV generation data.

        Returns:
            pd.DataFrame: The filtered dataset for the current date.
        """
        assert isinstance(data.index, pd.DatetimeIndex)

        current_date_data = data[
            (data.index.year == current_date.year)
            & (data.index.month == current_date.month)
            & (data.index.day == current_date.day)
        ]
        assert isinstance(current_date_data, pd.DataFrame)
        return current_date_data

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
        generation_current_date = list(current_date_data[column_name].values)
        assert isinstance(generation_current_date, list)
        return generation_current_date
