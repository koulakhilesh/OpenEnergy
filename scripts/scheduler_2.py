from abc import ABC, abstractmethod
import pandas as pd
import pyomo.environ as pyo
import logging
from typing import List

from .battery import Battery

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")



class IOptimizationModelBuilder(ABC):
    @abstractmethod
    def build_model(self, num_intervals: int, prices: List[float], battery: Battery, timestep_hours: float, max_cycles: float) -> pyo.ConcreteModel:
        pass

class IOptimizationSolver(ABC):
    @abstractmethod
    def solve(self, model: pyo.ConcreteModel, tee: bool):
        pass

class PyomoOptimizationModelBuilder(IOptimizationModelBuilder):
    def build_model(self, num_intervals: int, prices: List[float], battery: Battery, timestep_hours: float, max_cycles: float) -> pyo.ConcreteModel:
        self.prices = prices
        self.battery = battery
        self.timestep_hours = timestep_hours
        model = pyo.ConcreteModel(name="Battery_Schedule_Optimization")
        self._define_time_intervals(model, num_intervals)
        self._define_variables(model)
        self._define_objective_function(model)
        self._define_constraints(model, num_intervals, max_cycles)
        return model

    def _define_time_intervals(self, model, num_intervals):
        model.T = pyo.RangeSet(0, num_intervals - 1)

    def _define_variables(self, model):
        model.charge_vars = pyo.Var(model.T, within=pyo.NonNegativeReals, bounds=(0, self.battery.capacity_mwh), doc="Charge")
        model.discharge_vars = pyo.Var(model.T, within=pyo.NonNegativeReals, bounds=(0, self.battery.capacity_mwh), doc="Discharge")
        model.soc_vars = pyo.Var(model.T, within=pyo.NonNegativeReals, bounds=(0.05, 0.95), doc="SOC")
        model.energy_cycled_vars = pyo.Var(model.T, within=pyo.NonNegativeReals, doc="EnergyCycled")

    def _objective_rule(self, model):
        return sum((model.discharge_vars[t] * self.prices[t] * self.battery.discharge_efficiency / self.timestep_hours) -
                   (model.charge_vars[t] * self.prices[t] / (self.battery.charge_efficiency * self.timestep_hours))
                   for t in model.T)

    def _define_objective_function(self, model):
        model.objective = pyo.Objective(rule=self._objective_rule, sense=pyo.maximize, doc="Objective")

    def _charging_discharging_rule(self, model, t):
        return model.charge_vars[t] + model.discharge_vars[t] <= self.battery.capacity_mwh

    def _soc_update_rule(self, model, t):
        if t == 0:
            return pyo.Constraint.Skip
        else:
            return model.soc_vars[t] == model.soc_vars[t-1] + (model.charge_vars[t-1] * self.battery.charge_efficiency / self.battery.capacity_mwh) - (model.discharge_vars[t-1] / self.battery.discharge_efficiency / self.battery.capacity_mwh)

    def _energy_cycled_update_rule(self, model, t):
        if t == 0:
            return pyo.Constraint.Skip
        else:
            return model.energy_cycled_vars[t] == model.energy_cycled_vars[t-1] + model.charge_vars[t-1] * self.battery.charge_efficiency + model.discharge_vars[t-1] * (1 / self.battery.discharge_efficiency)

    def _define_constraints(self, model, num_intervals, max_cycles):
        model.initial_soc_constraint = pyo.Constraint(expr=model.soc_vars[0] == self.battery.initial_soc, doc="Initial SOC")
        model.charging_discharging_constraint = pyo.Constraint(model.T, rule=self._charging_discharging_rule, doc="Charging/Discharging")
        model.soc_update_constraint = pyo.Constraint(model.T, rule=self._soc_update_rule, doc="SOC Update")
        model.energy_cycled_update_constraint = pyo.Constraint(model.T, rule=self._energy_cycled_update_rule, doc="Energy Cycled Update")
        model.max_cycles_constraint = pyo.Constraint(expr=model.energy_cycled_vars[num_intervals-1] <= max_cycles * self.battery.capacity_mwh * 2, doc="Max Cycles")


class GLPKOptimizationSolver(IOptimizationSolver):
    def solve(self, model: pyo.ConcreteModel, tee: bool = False):
        solver = pyo.SolverFactory("glpk")
        result = solver.solve(model, tee=tee)

        # Check and log the solver's termination condition and status
        if result.solver.status == pyo.SolverStatus.ok and result.solver.termination_condition == pyo.TerminationCondition.optimal:
            logging.info("Solution is optimal.")
        elif result.solver.termination_condition in [pyo.TerminationCondition.infeasible, pyo.TerminationCondition.infeasibleOrUnbounded]:
            logging.warning("Solution is infeasible. Review model constraints.")
        elif result.solver.termination_condition == pyo.TerminationCondition.unbounded:
            logging.warning("Solution is unbounded. Review model objective and constraints.")
        elif result.solver.termination_condition == pyo.TerminationCondition.maxIterations:
            logging.warning("Maximum iterations reached. Solution may not be optimal.")
        else:
            logging.error(f"Unexpected solver status encountered: {result.solver.status}, {result.solver.termination_condition}")

        return result


class BatteryOptimizationScheduler:
    def __init__(self, battery: Battery, prices: List[float], model_builder: IOptimizationModelBuilder = None, solver: IOptimizationSolver= None):
        self.battery = battery
        self.prices = prices
        self.model_builder = model_builder if model_builder else PyomoOptimizationModelBuilder()
        self.solver = solver if solver else GLPKOptimizationSolver()

    def create_schedule(self, tee: bool = False) -> pd.DataFrame:
        num_intervals = len(self.prices)
        timestep_hours = 1.0  # Assuming 1 hour intervals for simplicity
        max_cycles = 5  # Example value, adjust as needed

        model = self.model_builder.build_model(num_intervals=num_intervals, prices=self.prices, battery=self.battery, timestep_hours=timestep_hours, max_cycles=max_cycles)
        result = self.solver.solve(model, tee)

        if result.solver.status == pyo.SolverStatus.ok and result.solver.termination_condition == pyo.TerminationCondition.optimal:
            return self._extract_schedule(model, num_intervals)
        else:
            logging.error(f"Optimization failed with status: {result.solver.status}, condition: {result.solver.termination_condition}")
            return pd.DataFrame()

    def _extract_schedule(self, model: pyo.ConcreteModel, num_intervals: int) -> pd.DataFrame:
        schedule_data = [{
            "Interval": i,
            "Charge": pyo.value(model.charge_vars[i]),
            "Discharge": pyo.value(model.discharge_vars[i]),
            "SOC": pyo.value(model.soc_vars[i])
        } for i in range(num_intervals)]
        return pd.DataFrame(schedule_data)
    

    