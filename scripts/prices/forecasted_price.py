import datetime
import typing as t

import pandas as pd
import pytz

from .interfaces import IDataProvider, IPriceData
from scripts.forecast.ts_forecast import IForecaster, IFeatureEngineer, TimeSeriesForecaster

from xgboost import XGBRegressor



class ForecastPriceModel(IPriceData, IForecaster):
    DAYS_IN_WEEK_PLUS_1 = 8

    def __init__(self, data_provider: IDataProvider, feature_engineer:IFeatureEngineer, model=XGBRegressor(random_state=42), history_length=7*24, forecast_length=24, interpolate: bool = True):
        self.data_provider = data_provider
        self.interpolate = interpolate
        self.forecaster = TimeSeriesForecaster(model, feature_engineer, history_length, forecast_length)
        self.data = self.data_provider.get_data(column_names=["GB_GBN_price_day_ahead"])
        if self.interpolate:
            self.data["GB_GBN_price_day_ahead"].interpolate(method="linear", inplace=True)

    def get_prices(self, date: datetime.date) -> t.Tuple[t.List[float], t.List[float]]:
        current_date = self._get_current_date(date)
        week_prior = self._get_week_prior(current_date)

        last_week_data = self._get_last_week_data(current_date, week_prior)


        # Forecast prices for the current date using last week's data
        forecasted_prices = self.forecast(last_week_data)

        current_date_data = self._get_current_date_data(current_date)
        prices_current_date = self._get_prices_current_date(current_date_data)

        return forecasted_prices, prices_current_date

    def _get_current_date(self, date: datetime.date) -> datetime.datetime:
        return datetime.datetime.combine(date, datetime.time.min).replace(tzinfo=pytz.utc)

    def _get_week_prior(self, current_date: datetime.datetime) -> datetime.datetime:
        return current_date - datetime.timedelta(days=self.DAYS_IN_WEEK_PLUS_1)

    def _get_last_week_data(self, current_date, week_prior):
        return self.data[(self.data.index >= week_prior) & (self.data.index < current_date)]

    def _get_current_date_data(self, current_date):
        return self.data[(self.data.index.year == current_date.year)&(self.data.index.month == current_date.month)&(self.data.index.day == current_date.day)]

    def _get_prices_current_date(self, current_date_data):
        return current_date_data["GB_GBN_price_day_ahead"].values

    def train(self, df, column_name='GB_GBN_price_day_ahead'):
        self.forecaster.train(df, column_name=column_name)

    def forecast(self, df, column_name='GB_GBN_price_day_ahead'):
        return self.forecaster.forecast(df, column_name=column_name)

    def evaluate(self, y_true, y_pred):
        return self.forecaster.evaluate(y_true, y_pred)

    def save_model(self, file_path):
        self.forecaster.save_model(file_path)

    @staticmethod
    def load_model(file_path):
        return ForecastPriceModel.load_model(file_path)
    