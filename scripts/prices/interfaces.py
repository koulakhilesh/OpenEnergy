import datetime
import typing as t
from abc import ABC, abstractmethod


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


class IDataProvider:
    def get_data(self):
        pass
