import datetime
import typing as t
from abc import ABC, abstractmethod

import pandas as pd


class IPriceData(ABC):
    @abstractmethod
    def get_prices(self, date: datetime.date) -> t.Tuple[t.List[float], t.List[float]]:
        pass


class IPriceEnvelopeGenerator(ABC):
    @abstractmethod
    def generate(self, date: datetime.date) -> t.List[float]:
        pass


class IPriceNoiseAdder(ABC):
    @abstractmethod
    def add(self, prices: t.List[float]) -> t.List[float]:
        pass


class IPriceDataHelper(ABC):
    @abstractmethod
    def get_current_date(self, date: datetime.date) -> datetime.datetime:
        pass

    @abstractmethod
    def get_week_prior(
        self, current_date: datetime.datetime, delta_days: int
    ) -> datetime.datetime:
        pass

    @abstractmethod
    def get_last_week_data(
        self,
        current_date: datetime.datetime,
        week_prior: datetime.datetime,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_current_date_data(
        self, current_date: datetime.datetime, data: pd.DataFrame
    ) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_prices_current_date(
        self, current_date_data: pd.DataFrame, column_name: str
    ) -> t.List[float]:
        pass
