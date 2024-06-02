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
    PRICE_COLUMN = "GB_GBN_price_day_ahead"
    TIMESTAMP_COLUMN = "utc_timestamp"

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
            column_names=[self.PRICE_COLUMN], timestamp_column=self.TIMESTAMP_COLUMN
        )
        self.helper = PriceDataHelper()
        if self.interpolate:
            self.data[self.PRICE_COLUMN].interpolate(method="linear", inplace=True)

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
            current_date_data, self.PRICE_COLUMN
        )

        return forecasted_prices, prices_current_date

    def train(self, df):
        self.forecaster.train(df, column_name=self.PRICE_COLUMN)

    def forecast(self, df):
        return self.forecaster.forecast(df, column_name=self.PRICE_COLUMN)

    def evaluate(self, y_true, y_pred):
        return self.forecaster.evaluate(y_true, y_pred)

    def save_model(self, file_path):
        self.forecaster.save_model(file_path)

    @staticmethod
    def load_model(file_path) -> IModel:
        return TimeSeriesForecaster.load_model(file_path)
