import typing as t

import pandas as pd
import pyomo.environ as pyo

from scripts.assets import Battery

from .interfaces import IModelBuilder, IModelExtractor, IModelSolver, IScheduler


class PyomoModelExtractor(IModelExtractor):
    """
    A class that extracts schedule data from a Pyomo model.

    Attributes:
        None

    Methods:
        extract_schedule(model: pyo.ConcreteModel, num_intervals: int) -> pd.DataFrame:
            Extracts schedule data from the given Pyomo model.

    """

    def extract_schedule(
        self, model: pyo.ConcreteModel, num_intervals: int
    ) -> pd.DataFrame:
        """
        Extracts schedule data from the given Pyomo model.

        Args:
            model (pyo.ConcreteModel): The Pyomo model from which to extract the schedule data.
            num_intervals (int): The number of intervals for which to extract the schedule data.

        Returns:
            pd.DataFrame: A DataFrame containing the extracted schedule data.

        """
        schedule_data = [
            {
                "Interval": i,
                "Charge": pyo.value(model.charge_vars[i]),
                "Discharge": pyo.value(model.discharge_vars[i]),
                "SOC": pyo.value(model.soc_vars[i]),
            }
            for i in range(num_intervals)
        ]
        return pd.DataFrame(schedule_data)


class BatteryOptimizationScheduler(IScheduler):
    """
    A class that represents a battery optimization scheduler.

    Attributes:
        battery (Battery): The battery object to be optimized.
        model_builder (IModelBuilder): The model builder object used to build the optimization model.
        solver (IModelSolver): The model solver object used to solve the optimization model.
        model_extractor (IModelExtractor): The model extractor object used to extract the optimized schedule.

    Methods:
        create_schedule(prices, timestep_hours, max_cycles, tee): Creates an optimized schedule based on the given prices.

    """

    def __init__(
        self,
        battery: Battery,
        model_builder: IModelBuilder,
        solver: IModelSolver,
        model_extractor: IModelExtractor,
    ):
        self.battery = battery
        self.model_builder = model_builder
        self.solver = solver
        self.model_extractor = model_extractor

    def create_schedule(
        self,
        prices: t.List[float],
        timestep_hours: float = 1.0,
        max_cycles: float = 5.0,
        tee: bool = False,
    ) -> pd.DataFrame:
        """
        Creates an optimized schedule based on the given prices.

        Args:
            prices (List[float]): A list of prices for each time interval.
            timestep_hours (float, optional): The duration of each time interval in hours. Defaults to 1.0.
            max_cycles (float, optional): The maximum number of charge-discharge cycles allowed for the battery. Defaults to 5.0.
            tee (bool, optional): Flag indicating whether to print solver output. Defaults to False.

        Returns:
            pd.DataFrame: A DataFrame representing the optimized schedule.

        Raises:
            Exception: If the optimization fails with a non-optimal status or condition.

        """
        num_intervals = len(prices)

        model = self.model_builder.build_model(
            num_intervals=num_intervals,
            prices=prices,
            battery=self.battery,
            timestep_hours=timestep_hours,
            max_cycles=max_cycles,
        )
        result = self.solver.solve(model, tee)

        if (
            result.solver.status == pyo.SolverStatus.ok
            and result.solver.termination_condition == pyo.TerminationCondition.optimal
        ):
            return self.model_extractor.extract_schedule(model, num_intervals)
        else:
            raise Exception(
                f"Optimization failed with status: {result.solver.status}, condition: {result.solver.termination_condition}"
            )
