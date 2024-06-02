import datetime
import typing as t

from scripts.forecast.ts_forecast import (
    DataPreprocessor,
    IFeatureEngineer,
    IForecaster,
    IModel,
    TimeSeriesForecaster,
)
from scripts.prices.helper import PriceDataHelper
from scripts.shared.interfaces import IDataProvider

from .interfaces import IPriceData


class ForecastPriceModel(IPriceData, IForecaster):
    DAYS_IN_WEEK_PLUS_1 = 8

    def __init__(
        self,
        data_provider: IDataProvider,
        feature_engineer: IFeatureEngineer,
        model: IModel,
        history_length=7 * 24,
        forecast_length=24,
        interpolate: bool = True,
    ):
        self.data_provider = data_provider
        self.interpolate = interpolate
        data_preprocessor = DataPreprocessor(
            feature_engineer, history_length, forecast_length
        )
        self.forecaster = TimeSeriesForecaster(model, data_preprocessor)
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
        week_prior = self.helper.get_week_prior(current_date, self.DAYS_IN_WEEK_PLUS_1)

        last_week_data = self.helper.get_last_week_data(
            current_date, week_prior, self.data
        )

        # Forecast prices for the current date using last week's data
        forecasted_prices = self.forecast(last_week_data)

        current_date_data = self.helper.get_current_date_data(current_date, self.data)
        prices_current_date = self.helper.get_prices_current_date(
            current_date_data, "GB_GBN_price_day_ahead"
        )

        return forecasted_prices, prices_current_date

    # def _get_current_date(self, date: datetime.date) -> datetime.datetime:
    #     return datetime.datetime.combine(date, datetime.time.min).replace(
    #         tzinfo=pytz.utc
    #     )

    # def _get_week_prior(self, current_date: datetime.datetime) -> datetime.datetime:
    #     return current_date - datetime.timedelta(days=self.DAYS_IN_WEEK_PLUS_1)

    # def _get_last_week_data(self, current_date, week_prior):
    #     return self.data[
    #         (self.data.index >= week_prior) & (self.data.index < current_date)
    #     ]

    # def _get_current_date_data(self, current_date):

    #     assert isinstance(self.data.index, pd.DatetimeIndex)

    #     current_date_data=self.data[
    #         (self.data.index.year == current_date.year)
    #         & (self.data.index.month == current_date.month)
    #         & (self.data.index.day == current_date.day)
    #     ]
    #     assert isinstance(current_date_data, pd.DataFrame)
    #     return current_date_data

    # def _get_prices_current_date(self, current_date_data):
    #     prices_current_date = current_date_data["GB_GBN_price_day_ahead"].values
    #     assert isinstance(prices_current_date, list)
    #     return prices_current_date

    def train(self, df, column_name="GB_GBN_price_day_ahead"):
        self.forecaster.train(df, column_name=column_name)

    def forecast(self, df, column_name="GB_GBN_price_day_ahead"):
        return self.forecaster.forecast(df, column_name=column_name)

    def evaluate(self, y_true, y_pred):
        return self.forecaster.evaluate(y_true, y_pred)

    def save_model(self, file_path):
        self.forecaster.save_model(file_path)

    @staticmethod
    def load_model(file_path):
        return ForecastPriceModel.load_model(file_path)
