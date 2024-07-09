import datetime
import typing as t

import pandas as pd

from scripts.pv_models.pv_data_helper import PVDataHelper
from scripts.shared.interfaces import IDataProvider

from .interfaces import IPVData


class HistoricalAveragePVGenerationModel(IPVData):
    """
    Represents a model for calculating historical average PV generation.

    Args:
        data_provider (IDataProvider): The data provider used to retrieve PV generation data.
        interpolate (bool, optional): Whether to interpolate missing values in the data. Defaults to True.
    """

    DAYS_IN_WEEK = 7
    GENERATION_COLUMN = "pv_generation"
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
            column_names=[self.GENERATION_COLUMN],
            timestamp_column=self.TIMESTAMP_COLUMN,
        )
        self.helper = PVDataHelper()
        self.prior_days = prior_days
        if self.interpolate:
            self.data[self.GENERATION_COLUMN].interpolate(method="linear", inplace=True)

    def get_generations(
        self, date: datetime.date
    ) -> t.Tuple[t.List[float], t.List[float]]:
        """
        Get the average PV generations for the last week and the generations for the current date.

        Args:
            date (datetime.date): The current date.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing the average PV generations for the last week
            and the generations for the current date.
        """
        current_date = self.helper.get_current_date(date)
        prior_date = self.helper.get_prior_date(current_date, self.DAYS_IN_WEEK)

        prior_data = self.helper.get_prior_data(current_date, prior_date, self.data)
        average_generations_last_week = self.get_average_generations_last_week(
            prior_data
        )

        current_date_data = self.helper.get_current_date_data(current_date, self.data)
        generations_current_date = self.helper.get_generation_current_date(
            current_date_data, self.GENERATION_COLUMN
        )

        return average_generations_last_week, generations_current_date

    def get_average_generations_last_week(
        self, last_week_data: pd.DataFrame
    ) -> t.List[float]:
        """
        Calculate the average PV generations for the last week.

        Args:
            last_week_data (pd.DataFrame): The PV generation data for the last week.

        Returns:
            List[float]: A list of average PV generations for each hour of the day.
        """
        assert isinstance(last_week_data.index, pd.DatetimeIndex)

        return (
            last_week_data.groupby(last_week_data.index.hour)[self.GENERATION_COLUMN]
            .mean()
            .tolist()
        )
