import datetime
import typing as t

import pandas as pd

from scripts.prices.helper import PriceDataHelper
from scripts.shared.interfaces import IDataProvider

from .interfaces import IPriceData


class HistoricalAveragePriceModel(IPriceData):
    """
    Represents a model for calculating historical average prices.

    Args:
        data_provider (IDataProvider): The data provider used to retrieve price data.
        interpolate (bool, optional): Whether to interpolate missing values in the data. Defaults to True.
    """

    DAYS_IN_WEEK = 7
    PRICE_COLUMN = "GB_GBN_price_day_ahead"
    TIMESTAMP_COLUMN = "utc_timestamp"

    def __init__(
        self,
        data_provider: IDataProvider,
        interpolate: bool = True,
        prior_days: int = DAYS_IN_WEEK,
    ):
        self.data_provider = data_provider
        self.interpolate = interpolate
        self.data = self.data_provider.get_data(
            column_names=[self.PRICE_COLUMN], timestamp_column=self.TIMESTAMP_COLUMN
        )
        self.helper = PriceDataHelper()
        self.prior_days = prior_days
        if self.interpolate:
            self.data[self.PRICE_COLUMN].interpolate(method="linear", inplace=True)

    def get_prices(self, date: datetime.date) -> t.Tuple[t.List[float], t.List[float]]:
        """
        Get the average prices for the last week and the prices for the current date.

        Args:
            date (datetime.date): The current date.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing the average prices for the last week
            and the prices for the current date.
        """
        current_date = self.helper.get_current_date(date)
        prior_date = self.helper.get_prior_date(current_date, self.DAYS_IN_WEEK)

        prior_data = self.helper.get_prior_data(current_date, prior_date, self.data)
        average_prices_last_week = self.get_average_prices_last_week(prior_data)

        current_date_data = self.helper.get_current_date_data(current_date, self.data)
        prices_current_date = self.helper.get_prices_current_date(
            current_date_data, self.PRICE_COLUMN
        )

        return average_prices_last_week, prices_current_date

    def get_average_prices_last_week(
        self, last_week_data: pd.DataFrame
    ) -> t.List[float]:
        """
        Calculate the average prices for the last week.

        Args:
            last_week_data (pd.DataFrame): The price data for the last week.

        Returns:
            List[float]: A list of average prices for each hour of the day.
        """
        assert isinstance(last_week_data.index, pd.DatetimeIndex)

        return (
            last_week_data.groupby(last_week_data.index.hour)[self.PRICE_COLUMN]
            .mean()
            .tolist()
        )
