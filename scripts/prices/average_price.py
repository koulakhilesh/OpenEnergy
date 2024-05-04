import datetime
import typing as t

import pandas as pd
import pytz

from .interfaces import IDataProvider, IPriceData


class CSVDataProvider(IDataProvider):
    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path

    def get_data(self) -> pd.DataFrame:
        return pd.read_csv(
            self.csv_file_path,
            parse_dates=["utc_timestamp"],
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
