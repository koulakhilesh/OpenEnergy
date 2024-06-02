import datetime
import typing as t

import pandas as pd

from scripts.prices.helper import PriceDataHelper
from scripts.shared.interfaces import IDataProvider

from .interfaces import IPriceData


class HistoricalAveragePriceModel(IPriceData):
    DAYS_IN_WEEK = 7

    def __init__(self, data_provider: IDataProvider, interpolate: bool = True):
        self.data_provider = data_provider
        self.interpolate = interpolate
        self.data = self.data_provider.get_data(
            column_names=["GB_GBN_price_day_ahead"], timestamp_column="utc_timestamp"
        )
        self.helper = PriceDataHelper()
        if self.interpolate:
            self.data["GB_GBN_price_day_ahead"].interpolate(
                method="linear", inplace=True
            )

    def get_prices(self, date: datetime.date) -> t.Tuple[t.List[float], t.List[float]]:
        current_date = self.helper.get_current_date(date)
        week_prior = self.helper.get_week_prior(current_date, self.DAYS_IN_WEEK)

        last_week_data = self.helper.get_last_week_data(
            current_date, week_prior, self.data
        )
        average_prices_last_week = self.get_average_prices_last_week(last_week_data)

        current_date_data = self.helper.get_current_date_data(current_date, self.data)
        prices_current_date = self.helper.get_prices_current_date(
            current_date_data, "GB_GBN_price_day_ahead"
        )

        return average_prices_last_week, prices_current_date

    def get_average_prices_last_week(
        self, last_week_data: pd.DataFrame
    ) -> t.List[float]:
        assert isinstance(last_week_data.index, pd.DatetimeIndex)

        return (
            last_week_data.groupby(last_week_data.index.hour)["GB_GBN_price_day_ahead"]
            .mean()
            .tolist()
        )
