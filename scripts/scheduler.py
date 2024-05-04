import logging
from abc import ABC, abstractmethod
from typing import List

import pandas as pd
import pyomo.environ as pyo

from .battery import Battery

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class IModelBuilder(ABC):
    @abstractmethod
    def build_model(
        self,
        num_intervals: int,
        prices: List[float],
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
    def define_time_intervals(self, model, num_intervals):
        pass

    @abstractmethod
    def define_variables(self, model):
        pass

    @abstractmethod
    def define_objective_function(self, model):
        pass

    @abstractmethod
    def define_constraints(self, model, num_intervals, max_cycles):
        pass


class IScheduler(ABC):
    @abstractmethod
    def create_schedule(
        self, prices: List[float], timestep_hours: float, max_cycles: float, tee: bool
    ) -> pd.DataFrame:
        pass


class PyomoOptimizationModelBuilder(IModelBuilder, IModelDefiner):
    def build_model(
        self,
        num_intervals: int,
        prices: List[float],
        battery: Battery,
        timestep_hours: float,
        max_cycles: float,
    ) -> pyo.ConcreteModel:
        self.prices = prices
        self.battery = battery
        self.timestep_hours = timestep_hours
        model = pyo.ConcreteModel(name="Battery_Schedule_Optimization")
        self.define_time_intervals(model, num_intervals)
        self.define_variables(model)
        self.define_objective_function(model)
        self.define_constraints(model, num_intervals, max_cycles)
        return model

    def define_time_intervals(self, model, num_intervals):
        model.T = pyo.RangeSet(0, num_intervals - 1)

    def define_variables(self, model):
        model.charge_vars = pyo.Var(
            model.T,
            within=pyo.NonNegativeReals,
            bounds=(0, self.battery.capacity_mwh),
            doc="Charge",
        )
        model.discharge_vars = pyo.Var(
            model.T,
            within=pyo.NonNegativeReals,
            bounds=(0, self.battery.capacity_mwh),
            doc="Discharge",
        )
        model.soc_vars = pyo.Var(
            model.T, within=pyo.NonNegativeReals, bounds=(0.05, 0.95), doc="SOC"
        )
        model.energy_cycled_vars = pyo.Var(
            model.T, within=pyo.NonNegativeReals, doc="EnergyCycled"
        )

    def _objective_rule(self, model):
        return sum(
            (
                model.discharge_vars[t]
                * self.prices[t]
                * self.battery.discharge_efficiency
                / self.timestep_hours
            )
            - (
                model.charge_vars[t]
                * self.prices[t]
                / (self.battery.charge_efficiency * self.timestep_hours)
            )
            for t in model.T
        )

    def define_objective_function(self, model):
        model.objective = pyo.Objective(
            rule=self._objective_rule, sense=pyo.maximize, doc="Objective"
        )

    def _charging_discharging_rule(self, model, t):
        return (
            model.charge_vars[t] + model.discharge_vars[t] <= self.battery.capacity_mwh
        )

    def _soc_update_rule(self, model, t):
        if t == 0:
            return pyo.Constraint.Skip
        else:
            return model.soc_vars[t] == model.soc_vars[t - 1] + (
                model.charge_vars[t - 1]
                * self.battery.charge_efficiency
                / self.battery.capacity_mwh
            ) - (
                model.discharge_vars[t - 1]
                / self.battery.discharge_efficiency
                / self.battery.capacity_mwh
            )

    def _energy_cycled_update_rule(self, model, t):
        if t == 0:
            return pyo.Constraint.Skip
        else:
            return model.energy_cycled_vars[t] == model.energy_cycled_vars[
                t - 1
            ] + model.charge_vars[
                t - 1
            ] * self.battery.charge_efficiency + model.discharge_vars[t - 1] * (
                1 / self.battery.discharge_efficiency
            )

    def define_constraints(self, model, num_intervals, max_cycles):
        model.initial_soc_constraint = pyo.Constraint(
            expr=model.soc_vars[0] == self.battery.initial_soc, doc="Initial SOC"
        )
        model.charging_discharging_constraint = pyo.Constraint(
            model.T, rule=self._charging_discharging_rule, doc="Charging/Discharging"
        )
        model.soc_update_constraint = pyo.Constraint(
            model.T, rule=self._soc_update_rule, doc="SOC Update"
        )
        model.energy_cycled_update_constraint = pyo.Constraint(
            model.T, rule=self._energy_cycled_update_rule, doc="Energy Cycled Update"
        )
        model.max_cycles_constraint = pyo.Constraint(
            expr=model.energy_cycled_vars[num_intervals - 1]
            <= max_cycles * self.battery.capacity_mwh * 2,
            doc="Max Cycles",
        )


class GLPKOptimizationSolver(IModelSolver):
    def solve(self, model: pyo.ConcreteModel, tee: bool = False):
        solver = pyo.SolverFactory("glpk")
        result = solver.solve(model, tee=tee)

        # Check and log the solver's termination condition and status
        match result.solver.termination_condition:
            case pyo.TerminationCondition.optimal if result.solver.status == pyo.SolverStatus.ok:
                logging.info("Solution is optimal.")
            case (
                pyo.TerminationCondition.infeasible
                | pyo.TerminationCondition.infeasibleOrUnbounded
            ):
                logging.warning("Solution is infeasible. Review model constraints.")
            case pyo.TerminationCondition.unbounded:
                logging.warning(
                    "Solution is unbounded. Review model objective and constraints."
                )
            case pyo.TerminationCondition.maxIterations:
                logging.warning(
                    "Maximum iterations reached. Solution may not be optimal."
                )
            case _:
                logging.error(
                    f"Unexpected solver status encountered: {result.solver.status}, {result.solver.termination_condition}"
                )

        return result


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
