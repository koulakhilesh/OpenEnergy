import typing as t
from abc import ABC, abstractmethod

import pandas as pd
import pyomo.environ as pyo

from scripts.assets import Battery


class IModelBuilder(ABC):
    @abstractmethod
    def build_model(
        self,
        num_intervals: int,
        prices: t.List[float],
        battery: Battery,
        timestep_hours: float,
        max_cycles: float,
    ) -> pyo.ConcreteModel:
        pass


class IModelSolver(ABC):
    @abstractmethod
    def solve(self, model: pyo.ConcreteModel, tee: bool):
        pass


class IModelExtractor(ABC):
    @abstractmethod
    def extract_schedule(
        self, model: pyo.ConcreteModel, num_intervals: int
    ) -> pd.DataFrame:
        pass


class IModelDefiner(ABC):
    @abstractmethod
    def define_time_intervals(self, model: pyo.ConcreteModel, num_intervals: int):
        pass

    @abstractmethod
    def define_variables(self, model: pyo.ConcreteModel):
        pass

    @abstractmethod
    def define_objective_function(self, model: pyo.ConcreteModel):
        pass

    @abstractmethod
    def define_constraints(
        self, model: pyo.ConcreteModel, num_intervals: int, max_cycles: float
    ):
        pass


class IScheduler(ABC):
    @abstractmethod
    def create_schedule(
        self, prices: t.List[float], timestep_hours: float, max_cycles: float, tee: bool
    ) -> pd.DataFrame:
        pass
