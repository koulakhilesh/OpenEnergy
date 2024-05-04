import logging
from typing import List

import pandas as pd
import pyomo.environ as pyo

from scripts.assets import Battery

from .interfaces import IModelBuilder, IModelExtractor, IModelSolver, IScheduler

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class PyomoModelExtractor(IModelExtractor):
    def extract_schedule(
        self, model: pyo.ConcreteModel, num_intervals: int
    ) -> pd.DataFrame:
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
        prices: List[float],
        timestep_hours: float = 1.0,
        max_cycles: float = 5.0,
        tee: bool = False,
    ) -> pd.DataFrame:
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
