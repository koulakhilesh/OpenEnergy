import datetime
import typing as t

import pandas as pd

from .interfaces import IWindDataHelper


class WindDataHelper(IWindDataHelper):
    """Implementation of IWindDataHelper for wind generation data operations."""

    def get_current_date(self, date: datetime.date) -> datetime.datetime:
        """Get the current date and time.

        Args:
            date (datetime.date): The current date.

        Returns:
            datetime.datetime: The current date and time.
        """
        return datetime.datetime.combine(date, datetime.time())

    def get_prior_date(
        self, current_date: datetime.datetime, delta_days: int
    ) -> datetime.datetime:
        """Get the date a certain number of days before the current date.

        Args:
            current_date (datetime.datetime): The current date and time.
            delta_days (int): The number of days before the current date to retrieve.

        Returns:
            datetime.datetime: The date before the current date by the specified number of days.
        """
        return current_date - datetime.timedelta(days=delta_days)

    def get_prior_data(
        self,
        current_date: datetime.datetime,
        prior_date: datetime.datetime,
        data_source,
    ) -> pd.DataFrame:
        """Get the wind generation data for the period between two dates.

        Args:
            current_date (datetime.datetime): The current date and time.
            prior_date (datetime.datetime): The prior date and time.
            data_source: Either a wind data interface for retrieving wind generation data,
                        or a pandas DataFrame containing historical data.

        Returns:
            pd.DataFrame: A DataFrame containing the wind generation data for the specified period.
        """
        # Check if data_source is a DataFrame (loaded data) or an interface
        if isinstance(data_source, pd.DataFrame):
            # Filter the DataFrame for the date range
            return data_source[(data_source.index >= prior_date) & (data_source.index < current_date)]
        else:
            # Use the interface to get data (legacy behavior)
            data = []
            current = prior_date
            while current <= current_date:
                generations, _ = data_source.get_generation(current.date())
                for hour, generation in enumerate(generations):
                    data.append(
                        {"date": current.date(), "hour": hour, "generation": generation}
                    )
                current += datetime.timedelta(days=1)

            return pd.DataFrame(data)

    def get_current_date_data(
        self, current_date: datetime.datetime, data: pd.DataFrame
    ) -> pd.DataFrame:
        """Get the wind generation data for the current date.

        Args:
            current_date (datetime.datetime): The current date.
            data (pd.DataFrame): The dataset containing wind generation data.

        Returns:
            pd.DataFrame: The filtered dataset for the current date.
        """
        assert isinstance(data.index, pd.DatetimeIndex)

        current_date_data = data[
            (data.index.year == current_date.year)
            & (data.index.month == current_date.month)
            & (data.index.day == current_date.day)
        ]
        assert isinstance(current_date_data, pd.DataFrame)
        return current_date_data

    def get_generation_current_date(
        self, current_date_data: pd.DataFrame, column_name: str
    ) -> t.List[float]:
        """Get the wind generation data for the current date.

        Args:
            current_date_data (pd.DataFrame): The dataset for the current date.
            column_name (str): The name of the column containing the wind generation data.

        Returns:
            List[float]: The wind generation data for the current date.
        """
        generation_current_date = list(current_date_data[column_name].values)
        assert isinstance(generation_current_date, list)
        return generation_current_date

    def get_prior_data_as_list(
        self,
        current_date: datetime.datetime,
        prior_date: datetime.datetime,
        data_source,
    ) -> t.List[float]:
        """Get the wind generation data for the period between two dates as a list.

        Args:
            current_date (datetime.datetime): The current date and time.
            prior_date (datetime.datetime): The prior date and time.
            data_source: Either a wind data interface for retrieving wind generation data,
                        or a pandas DataFrame containing historical data.

        Returns:
            List[float]: A list containing the wind generation data for the specified period.
        """
        df = self.get_prior_data(current_date, prior_date, data_source)
        return df["generation"].tolist() if "generation" in df.columns else []

    def get_seasonal_trend(
        self, date: datetime.date, base_generation: t.List[float]
    ) -> t.List[float]:
        """Apply seasonal trends to base wind generation data.

        Wind is typically stronger in winter months and during certain times of day.

        Args:
            date (datetime.date): The date for seasonal calculations.
            base_generation (List[float]): Base wind generation values.

        Returns:
            List[float]: Wind generation data with seasonal adjustments.
        """
        # Winter months (Dec, Jan, Feb) have higher wind
        # Summer months (Jun, Jul, Aug) have lower wind
        month = date.month
        if month in [12, 1, 2]:  # Winter
            seasonal_factor = 1.3
        elif month in [6, 7, 8]:  # Summer
            seasonal_factor = 0.8
        elif month in [3, 4, 5, 9, 10, 11]:  # Spring/Fall
            seasonal_factor = 1.0
        else:
            seasonal_factor = 1.0

        return [gen * seasonal_factor for gen in base_generation]

    def get_wind_speed_factor(self, hour: int) -> float:
        """Get wind speed factor for a specific hour of the day.

        Wind speed typically peaks in afternoon/evening hours.

        Args:
            hour (int): Hour of the day (0-23).

        Returns:
            float: Wind speed factor for the given hour.
        """
        # Wind speed patterns: higher in afternoon/evening
        if 6 <= hour <= 10:  # Morning - moderate
            return 0.9
        elif 11 <= hour <= 17:  # Afternoon - high
            return 1.2
        elif 18 <= hour <= 22:  # Evening - highest
            return 1.3
        else:  # Night/early morning - low
            return 0.7
