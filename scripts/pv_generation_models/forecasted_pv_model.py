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
from scripts.pv_models.pv_data_helper import PVDataHelper
from scripts.shared.interfaces import IDataProvider

from .interfaces import IPVData

warnings.simplefilter(action="ignore", category=pd.errors.SettingWithCopyWarning)


class ForecastPVGenerationModel(IPVData, IForecaster):
    """
    A class representing a forecast PV generation model.

    This class implements the `IPVGenerationData` and `IForecaster` interfaces and provides methods for training, forecasting,
    and evaluating PV generation.

    Attributes:
        DAYS_IN_WEEK (int): The number of days in a week.
        GENERATION_COLUMN (str): The name of the column containing the PV generation data.
        TIMESTAMP_COLUMN (str): The name of the column containing the timestamps.

    Args:
        data_provider (IDataProvider): An object that provides access to the PV generation data.
        feature_engineer (IFeatureEngineer): An object that performs feature engineering on the data.
        model (IModel): A machine learning model for forecasting.
        history_length (int, optional): The length of the historical data used for training. Defaults to 7 * 24.
        forecast_length (int, optional): The length of the forecasted data. Defaults to 24.
        interpolate (bool, optional): Whether to interpolate missing values in the PV generation data. Defaults to True.
        prior_days (int, optional): The number of days prior to the current date to consider for forecasting. Defaults to 7.
    """

    DAYS_IN_WEEK = 7
    GENERATION_COLUMN = "pv_generation"
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
            column_names=[self.GENERATION_COLUMN],
            timestamp_column=self.TIMESTAMP_COLUMN,
        )
        self.helper = PVDataHelper()
        self._prior_days = prior_days

        if self.interpolate:
            self.data[self.GENERATION_COLUMN].interpolate(method="linear", inplace=True)

    def get_generations(
        self, date: datetime.date
    ) -> t.Tuple[t.List[float], t.List[float]]:
        """
        Get the forecasted PV generations and actual generations for a given date.

        Args:
            date (datetime.date): The date for which to get the generations.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing the forecasted PV generations and actual generations.
        """
        current_date = self.helper.get_current_date(date)
        prior_date = self.helper.get_prior_date(current_date, self._prior_days)

        prior_data = self.helper.get_prior_data(current_date, prior_date, self.data)
        forecasted_generations = self.forecast(prior_data)

        current_date_data = self.helper.get_current_date_data(current_date, self.data)
        generations_current_date = self.helper.get_generation_current_date(
            current_date_data, self.GENERATION_COLUMN
        )

        return forecasted_generations, generations_current_date

    def train(self, df):
        """
        Train the forecast PV generation model.

        Args:
            df (pandas.DataFrame): The training data.
        """
        self.forecaster.train(df, column_name=self.GENERATION_COLUMN, include_lead=True)

    def forecast(self, df):
        """
        Forecast the PV generations.

        Args:
            df (pandas.DataFrame): The data to use for forecasting.
        """
        return (
            self.forecaster.forecast(
                df, column_name=self.GENERATION_COLUMN, include_lead=False
            )
            .flatten()
            .tolist()
        )

    def evaluate(self, y_true, y_pred):
        """
        Evaluate the forecasted PV generations.

        Args:
            y_true (numpy.ndarray): The true PV generations.
            y_pred (numpy.ndarray): The forecasted PV generations.

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
