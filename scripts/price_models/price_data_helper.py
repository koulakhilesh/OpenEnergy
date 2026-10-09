import datetime
import typing as t

import pandas as pd
import pytz  # type: ignore

from .interfaces import IPriceDataHelper


class PriceDataHelper(IPriceDataHelper):
    """Helper class for manipulating price data."""

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
        return current_date - datetime.timedelta(days=delta_days)

    def get_prior_data(
        self,
        current_date: datetime.datetime,
        prior_date: datetime.datetime,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        return data[(data.index >= prior_date) & (data.index < current_date)]

    def get_current_date_data(
        self, current_date: datetime.datetime, data: pd.DataFrame
    ) -> pd.DataFrame:
        """Get the data for the current date.

        Args:
            current_date (datetime.datetime): The current date.
            data (pd.DataFrame): The data containing price information.

        Returns:
            pd.DataFrame: The data for the current date.
        """
        assert isinstance(data.index, pd.DatetimeIndex)

        current_date_data = data[
            (data.index.year == current_date.year)
            & (data.index.month == current_date.month)
            & (data.index.day == current_date.day)
        ]
        assert isinstance(current_date_data, pd.DataFrame)
        return current_date_data

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
        prices_current_date = list(current_date_data[column_name].values)
        assert isinstance(prices_current_date, list)
        return prices_current_date
