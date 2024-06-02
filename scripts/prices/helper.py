import datetime
import typing as t

import pandas as pd
import pytz

from .interfaces import IPriceDataHelper


class PriceDataHelper(IPriceDataHelper):
    def get_current_date(self, date: datetime.date) -> datetime.datetime:
        return datetime.datetime.combine(date, datetime.time.min).replace(
            tzinfo=pytz.utc
        )

    def get_week_prior(
        self, current_date: datetime.datetime, delta_days: int
    ) -> datetime.datetime:
        return current_date - datetime.timedelta(days=delta_days)

    def get_last_week_data(
        self,
        current_date: datetime.datetime,
        week_prior: datetime.datetime,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        return data[(data.index >= week_prior) & (data.index < current_date)]

    def get_current_date_data(
        self, current_date: datetime.datetime, data: pd.DataFrame
    ) -> pd.DataFrame:
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
        prices_current_date = list(current_date_data[column_name].values)
        assert isinstance(prices_current_date, list)
        return prices_current_date
