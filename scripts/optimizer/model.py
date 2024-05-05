import typing as t

import pyomo.environ as pyo

from scripts.assets import Battery
from scripts.shared import Logger

from .interfaces import IModelBuilder, IModelDefiner, IModelSolver


class PyomoOptimizationModelBuilder(IModelBuilder, IModelDefiner):
    def build_model(
        self,
        num_intervals: int,
        prices: t.List[float],
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

    def define_time_intervals(self, model: pyo.ConcreteModel, num_intervals: int):
        model.T = pyo.RangeSet(0, num_intervals - 1)

    def define_variables(self, model: pyo.ConcreteModel):
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

    def _objective_rule(self, model: pyo.ConcreteModel):
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

    def define_objective_function(self, model: pyo.ConcreteModel):
        model.objective = pyo.Objective(
            rule=self._objective_rule, sense=pyo.maximize, doc="Objective"
        )

    def _charging_discharging_rule(self, model: pyo.ConcreteModel, t: int):
        return (
            model.charge_vars[t] + model.discharge_vars[t] <= self.battery.capacity_mwh
        )

    def _soc_update_rule(self, model: pyo.ConcreteModel, t: int):
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

    def _energy_cycled_update_rule(self, model: pyo.ConcreteModel, t: int):
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

    def define_constraints(
        self, model: pyo.ConcreteModel, num_intervals: int, max_cycles: float
    ):
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
    def __init__(self, log_level: int = Logger.INFO):
        self.logger = Logger(log_level)

    def solve(self, model: pyo.ConcreteModel, tee: bool = False):
        solver = pyo.SolverFactory("glpk")
        result = solver.solve(model, tee=tee)

        # Check and log the solver's termination condition and status
        match result.solver.termination_condition:
            case pyo.TerminationCondition.optimal if result.solver.status == pyo.SolverStatus.ok:
                self.logger.debug("Solution is optimal.")
            case (
                pyo.TerminationCondition.infeasible
                | pyo.TerminationCondition.infeasibleOrUnbounded
            ):
                self.logger.warning("Solution is infeasible. Review model constraints.")
            case pyo.TerminationCondition.unbounded:
                self.logger.warning(
                    "Solution is unbounded. Review model objective and constraints."
                )
            case pyo.TerminationCondition.maxIterations:
                self.logger.warning(
                    "Maximum iterations reached. Solution may not be optimal."
                )
            case _:
                self.logger.error(
                    f"Unexpected solver status encountered: {result.solver.status}, {result.solver.termination_condition}"
                )

        return result
