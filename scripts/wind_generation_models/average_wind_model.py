import datetime
import typing as t

import pandas as pd

from scripts.shared.interfaces import IDataProvider

from .interfaces import IWindData
from .wind_data_helper import WindDataHelper


class HistoricalAverageWindGenerationModel(IWindData):
    """
    A historical average wind generation model.

    This model calculates wind generation based on historical averages
    for similar dates and times, providing a baseline forecast.
    """

    DAYS_IN_WEEK = 7
    GENERATION_COLUMN = "wind_generation"
    TIMESTAMP_COLUMN = "utc_timestamp"

    def __init__(
        self,
        data_provider: IDataProvider,
        wind_data_helper: t.Optional[WindDataHelper] = None,
        lookback_days: int = 30,
        capacity_kw: float = 1000.0,
        interpolate: bool = True,
    ):
        """
        Initialize the historical average wind generation model.

        Args:
            data_provider (IDataProvider): Provider for historical wind data.
            wind_data_helper (WindDataHelper): Helper for wind data operations.
            lookback_days (int): Number of days to look back for historical average.
            capacity_kw (float): Maximum wind generation capacity in kW.
            interpolate (bool): Whether to interpolate missing values in the data.
        """
        self.data_provider = data_provider
        self.wind_data_helper = wind_data_helper or WindDataHelper()
        self.lookback_days = lookback_days
        self.capacity_kw = capacity_kw
        self.interpolate = interpolate
        
        # Load data in constructor like PV and price models
        self.data = self.data_provider.get_data(
            column_names=[self.GENERATION_COLUMN],
            timestamp_column=self.TIMESTAMP_COLUMN,
        )
        
        if self.interpolate and self.data is not None and not self.data.empty:
            self.data = self.data.copy()
            self.data[self.GENERATION_COLUMN] = self.data[self.GENERATION_COLUMN].interpolate(method="linear")

    def get_generation(
        self, date: datetime.date
    ) -> t.Tuple[t.List[float], t.List[float]]:
        """
        Get the wind generation data for a specific date based on historical averages.

        Args:
            date (datetime.date): The date for which to retrieve the wind generation data.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing two lists of floats.
                The first list represents the average generated power in kW for each hour,
                and the second list represents the potential generation capacity in kW.
        """
        try:
            # Follow the same pattern as PV and price models
            current_date = self.wind_data_helper.get_current_date(date)
            prior_date = self.wind_data_helper.get_prior_date(current_date, self.lookback_days)

            # Get historical averages from loaded data
            if self.data is not None and not self.data.empty:
                prior_data = self.wind_data_helper.get_prior_data(
                    current_date, prior_date, self.data
                )
                average_generations = self.get_average_generations_lookback_period(prior_data)
            else:
                # Fallback to default pattern if no data
                average_generations = self._get_default_pattern_list(date)

            # Get current date data if available
            potential_generation = [self.capacity_kw] * 24
            
            if self.data is not None and not self.data.empty:
                try:
                    current_date_data = self.wind_data_helper.get_current_date_data(current_date, self.data)
                    if not current_date_data.empty:
                        current_generations = self.wind_data_helper.get_generation_current_date(
                            current_date_data, self.GENERATION_COLUMN
                        )
                        # Use current data if available, otherwise use averages
                        if len(current_generations) == 24:
                            actual_generation = current_generations
                        else:
                            actual_generation = average_generations
                    else:
                        actual_generation = average_generations
                except Exception:
                    actual_generation = average_generations
            else:
                actual_generation = average_generations

            # Apply seasonal trends
            adjusted_generation = self.wind_data_helper.get_seasonal_trend(
                date, actual_generation
            )

            # Ensure generation doesn't exceed capacity
            final_generation = [
                min(gen, self.capacity_kw) for gen in adjusted_generation
            ]

            return final_generation, potential_generation

        except Exception:
            # Fallback to default pattern on any error
            return self._get_default_pattern(date)

    def get_average_generations_lookback_period(
        self, lookback_data: pd.DataFrame
    ) -> t.List[float]:
        """
        Calculate the average wind generations for the lookback period.

        Args:
            lookback_data (pd.DataFrame): The wind generation data for the lookback period.

        Returns:
            List[float]: A list of average wind generations for each hour of the day.
        """
        if lookback_data.empty:
            return self._get_default_pattern_list(datetime.date.today())
            
        assert isinstance(lookback_data.index, pd.DatetimeIndex)

        return (
            lookback_data.groupby(lookback_data.index.hour)[self.GENERATION_COLUMN]
            .mean()
            .reindex(range(24), fill_value=0.0)  # Ensure we have all 24 hours
            .tolist()
        )

    def _get_default_pattern_list(self, date: datetime.date) -> t.List[float]:
        """Get default wind generation pattern as a list."""
        return [self._get_hourly_default(hour, date) for hour in range(24)]

    def _get_default_pattern(
        self, date: datetime.date
    ) -> t.Tuple[t.List[float], t.List[float]]:
        """Get default wind generation pattern when no historical data is available."""
        base_pattern = self._get_default_pattern_list(date)

        # Apply seasonal trends
        adjusted_pattern = self.wind_data_helper.get_seasonal_trend(date, base_pattern)

        # Potential generation is the maximum capacity
        potential_generation = [self.capacity_kw] * 24

        return adjusted_pattern, potential_generation

    def _get_hourly_default(self, hour: int, date: datetime.date) -> float:
        """Get default generation for a specific hour."""
        # Default wind pattern - typically stronger in afternoon/evening
        wind_factor = self.wind_data_helper.get_wind_speed_factor(hour)
        base_generation = self.capacity_kw * 0.4  # 40% capacity factor as baseline

        return base_generation * wind_factor
