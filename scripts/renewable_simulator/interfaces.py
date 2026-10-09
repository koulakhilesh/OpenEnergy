import datetime
import typing as t
from abc import ABC, abstractmethod

import pandas as pd


class IRenewableData(ABC):
    """Interface for retrieving renewable energy generation data."""

    @abstractmethod
    def get_generation(
        self, date: datetime.date
    ) -> t.Tuple[t.List[float], t.List[float]]:
        """Get the renewable generation data for a specific date.

        Args:
            date (datetime.date): The date for which to retrieve generation data.

        Returns:
            Tuple[List[float], List[float]]: A tuple containing two lists of floats.
                The first list represents the generated power in kW for each hour of the day,
                and the second list represents the estimated potential generation in kW.
        """
        pass


class IRenewablePortfolio(ABC):
    """Interface for managing a portfolio of renewable energy assets."""

    @abstractmethod
    def calculate_total_generation(
        self, date: datetime.date
    ) -> t.Tuple[t.List[float], t.List[float]]:
        """Calculate total generation from all renewable assets.

        Args:
            date (datetime.date): The date for generation calculation.

        Returns:
            Tuple[List[float], List[float]]: Total actual and potential generation.
        """
        pass

    @abstractmethod
    def get_asset_breakdown(
        self, date: datetime.date
    ) -> t.Dict[str, t.Tuple[t.List[float], t.List[float]]]:
        """Get generation breakdown by asset type.

        Args:
            date (datetime.date): The date for generation calculation.

        Returns:
            Dict: Asset type mapped to (actual, potential) generation tuples.
        """
        pass

    @abstractmethod
    def optimize_dispatch(
        self, date: datetime.date, prices: t.List[float]
    ) -> pd.DataFrame:
        """Optimize renewable energy dispatch based on prices.

        Args:
            date (datetime.date): The date for optimization.
            prices (List[float]): Hourly electricity prices.

        Returns:
            pd.DataFrame: Optimized dispatch schedule.
        """
        pass


class IRenewableForecaster(ABC):
    """Interface for forecasting renewable energy generation."""

    @abstractmethod
    def forecast_generation(
        self, date: datetime.date, horizon_hours: int = 24
    ) -> t.Dict[str, t.List[float]]:
        """Forecast renewable generation for multiple sources.

        Args:
            date (datetime.date): Starting date for forecast.
            horizon_hours (int): Forecast horizon in hours.

        Returns:
            Dict: Asset type mapped to forecasted generation lists.
        """
        pass

    @abstractmethod
    def get_forecast_uncertainty(
        self, date: datetime.date, horizon_hours: int = 24
    ) -> t.Dict[str, t.List[float]]:
        """Get forecast uncertainty bounds.

        Args:
            date (datetime.date): Starting date for forecast.
            horizon_hours (int): Forecast horizon in hours.

        Returns:
            Dict: Asset type mapped to uncertainty bounds.
        """
        pass


class IRenewableOptimizer(ABC):
    """Interface for optimizing renewable energy systems."""

    @abstractmethod
    def optimize_portfolio(
        self,
        solar_capacity: float,
        wind_capacity: float,
        battery_capacity: float,
        prices: t.List[float],
        date: datetime.date,
    ) -> t.Dict[str, t.Any]:
        """Optimize renewable portfolio operation.

        Args:
            solar_capacity (float): Solar capacity in MW.
            wind_capacity (float): Wind capacity in MW.
            battery_capacity (float): Battery capacity in MWh.
            prices (List[float]): Hourly electricity prices.
            date (datetime.date): Operating date.

        Returns:
            Dict: Optimization results including dispatch schedules and revenues.
        """
        pass
