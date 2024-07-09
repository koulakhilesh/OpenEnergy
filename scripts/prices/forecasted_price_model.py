import datetime
import typing as t
import warnings

import pandas as pd

from scripts.forecast import (
    DataPreprocessor,
    IFeatureEngineer,
    IForecaster,
    IModel,
    TimeSeriesForecaster,
)
from scripts.prices.price_data_helper import PriceDataHelper
from scripts.shared.interfaces import IDataProvider

from .interfaces import IPriceData

warnings.simplefilter(action="ignore", category=pd.errors.SettingWithCopyWarning)


class ForecastPriceModel(IPriceData, IForecaster):
    """
    A class representing a forecast price model.

    This class implements the `IPriceData` and `IForecaster` interfaces and provides methods for training, forecasting,
    and evaluating prices.

    Attributes:
        DAYS_IN_WEEK (int): The number of days in a week e.
        PRICE_COLUMN (str): The name of the column containing the price data.
        TIMESTAMP_COLUMN (str): The name of the column containing the timestamps.

    Args:
        data_provider (IDataProvider): An object that provides access to the price data.
        feature_engineer (IFeatureEngineer): An object that performs feature engineering on the data.
        model (IModel): A machine learning model for forecasting.
        history_length (int, optional): The length of the historical data used for training. Defaults to 7 * 24.
        forecast_length (int, optional): The length of the forecasted data. Defaults to 24.
        interpolate (bool, optional): Whether to interpolate missing values in the price data. Defaults to True.
    """

    DAYS_IN_WEEK = 7
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
        prior_days: int = DAYS_IN_WEEK,
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
        self._prior_days = prior_days

        if self.interpolate:
            self.data[self.PRICE_COLUMN].interpolate(method="linear", inplace=True)

    def get_prices(self, date: datetime.date) -> t.Tuple[t.List[float], t.List[float]]:
        """
        Get the forecasted prices and actual prices for a given date.

        Args:
            date (datetime.date): The date for which to get the prices.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing the forecasted prices and actual prices.
        """
        current_date = self.helper.get_current_date(date)
        prior_date = self.helper.get_prior_date(current_date, self._prior_days)

        prior_data = self.helper.get_prior_data(current_date, prior_date, self.data)
        forecasted_prices = self.forecast(prior_data)

        current_date_data = self.helper.get_current_date_data(current_date, self.data)
        prices_current_date = self.helper.get_prices_current_date(
            current_date_data, self.PRICE_COLUMN
        )

        return forecasted_prices, prices_current_date

    def train(self, df):
        """
        Train the forecast price model.

        Args:
            df (pandas.DataFrame): The training data.
        """
        self.forecaster.train(df, column_name=self.PRICE_COLUMN, include_lead=True)

    def forecast(self, df):
        """
        Forecast the prices.

        Args:
            df (pandas.DataFrame): The data to use for forecasting.
        """
        return (
            self.forecaster.forecast(
                df, column_name=self.PRICE_COLUMN, include_lead=False
            )
            .flatten()
            .tolist()
        )

    def evaluate(self, y_true, y_pred):
        """
        Evaluate the forecasted prices.

        Args:
            y_true (numpy.ndarray): The true prices.
            y_pred (numpy.ndarray): The forecasted prices.

        Returns:
            float: The evaluation metric.
        """
        return self.forecaster.evaluate(y_true, y_pred)

    def save_model(self, file_path):
        """
        Save the trained model to a file.

        Args:
            file_path (str): The path to the file.
        """
        self.forecaster.save_model(file_path)

    @staticmethod
    def load_model(file_path) -> IModel:
        """
        Load a trained model from a file.

        Args:
            file_path (str): The path to the file.

        Returns:
            IModel: The loaded model.
        """
        return TimeSeriesForecaster.load_model(file_path)
