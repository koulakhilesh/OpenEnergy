import typing as t
from abc import ABC, abstractmethod

import pandas as pd
import pyomo.environ as pyo

from scripts.assets import Battery


class IModelBuilder(ABC):
    """
    Interface for model builders.

    This interface defines the contract for classes that build optimization models.

    Attributes:
        None

    Methods:
        build_model(num_intervals, prices, battery, timestep_hours, max_cycles):
            Builds an optimization model based on the given parameters.

    """

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
    """
    Interface for model solvers.

    This interface defines the contract for classes that implement model solving functionality.
    """

    @abstractmethod
    def solve(self, model: pyo.ConcreteModel, tee: bool):
        """
        Solve the given model.

        Parameters:
        - model: The pyomo.ConcreteModel object representing the optimization model.
        - tee: A boolean flag indicating whether to display solver output.

        Returns:
        None
        """
        pass


class IModelExtractor(ABC):
    """
    Interface for extracting schedule from a Pyomo model.

    This interface defines the method `extract_schedule` that should be implemented
    by classes that extract schedule information from a Pyomo model.

    Attributes:
        None

    Methods:
        extract_schedule(model: pyo.ConcreteModel, num_intervals: int) -> pd.DataFrame:
            Extracts the schedule from the given Pyomo model and returns it as a pandas DataFrame.

    """

    @abstractmethod
    def extract_schedule(
        self, model: pyo.ConcreteModel, num_intervals: int
    ) -> pd.DataFrame:
        pass


class IModelDefiner(ABC):
    """
    Interface for defining optimization models.
    """

    @abstractmethod
    def define_time_intervals(self, model: pyo.ConcreteModel, num_intervals: int):
        """
        Abstract method for defining time intervals in the optimization model.

        Parameters:
        - model: The optimization model.
        - num_intervals: The number of time intervals.

        Returns:
        None
        """

        pass

    @abstractmethod
    def define_variables(self, model: pyo.ConcreteModel):
        """
        Abstract method for defining variables in the optimization model.

        Parameters:
        - model: The optimization model.

        Returns:
        None
        """

        pass

    @abstractmethod
    def define_objective_function(self, model: pyo.ConcreteModel):
        """
        Abstract method for defining the objective function in the optimization model.

        Parameters:
        - model: The optimization model.

        Returns:
        None
        """

        pass

    @abstractmethod
    def define_constraints(
        self, model: pyo.ConcreteModel, num_intervals: int, max_cycles: float
    ):
        """
        Abstract method for defining constraints in the optimization model.

        Parameters:
        - model: The optimization model.
        - num_intervals: The number of time intervals.
        - max_cycles: The maximum number of cycles.

        Returns:
        None
        """

        pass


class IScheduler(ABC):
    """
    Interface for creating schedules based on prices.

    This interface defines the contract for classes that implement scheduling algorithms
    based on energy prices.

    Attributes:
        None

    Methods:
        create_schedule: Creates a schedule based on energy prices.

    """

    @abstractmethod
    def create_schedule(
        self, prices: t.List[float], timestep_hours: float, max_cycles: float, tee: bool
    ) -> pd.DataFrame:
        """
        Creates a schedule based on energy prices.

        Args:
            prices (List[float]): A list of energy prices.
            timestep_hours (float): The duration of each timestep in hours.
            max_cycles (float): The maximum number of cycles allowed in the schedule.
            tee (bool): A flag indicating whether to print debug information.

        Returns:
            pd.DataFrame: A DataFrame representing the schedule.

        """
        pass
