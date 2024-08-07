import typing as t

import pyomo.environ as pyo

from scripts.assets import Battery
from scripts.shared import Logger

from .interfaces import IModelBuilder, IModelDefiner, IModelSolver


class PyomoOptimizationModelBuilder(IModelBuilder, IModelDefiner):
    """A class that builds a Pyomo optimization model for battery scheduling."""

    def build_model(
        self,
        num_intervals: int,
        prices: t.List[float],
        battery: Battery,
        timestep_hours: float,
        max_cycles: float,
    ) -> pyo.ConcreteModel:
        """
        Build the Pyomo optimization model.

        Args:
            num_intervals (int): The number of time intervals.
            prices (List[float]): The list of electricity prices for each time interval.
            battery (Battery): The battery object.
            timestep_hours (float): The duration of each time interval in hours.
            max_cycles (float): The maximum number of cycles allowed for the battery.

        Returns:
            pyo.ConcreteModel: The Pyomo optimization model.
        """
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
        """
        Define the time intervals for the optimization model.

        Args:
            model (pyo.ConcreteModel): The Pyomo optimization model.
            num_intervals (int): The number of time intervals.
        """
        model.T = pyo.RangeSet(0, num_intervals - 1)

    def define_variables(self, model: pyo.ConcreteModel):
        """
        Define the variables for the optimization model.

        Args:
            model (pyo.ConcreteModel): The Pyomo optimization model.
        """
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
        """
        Define the objective function rule for the optimization model.

        Args:
            model (pyo.ConcreteModel): The Pyomo optimization model.

        Returns:
            Expression: The expression representing the objective function.
        """
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
        """
        Define the objective function for the optimization model.

        Args:
            model (pyo.ConcreteModel): The Pyomo optimization model.
        """
        model.objective = pyo.Objective(
            rule=self._objective_rule, sense=pyo.maximize, doc="Objective"
        )

    def _charging_discharging_rule(self, model: pyo.ConcreteModel, t: int):
        """
        Define the charging and discharging constraint rule for the optimization model.

        Args:
            model (pyo.ConcreteModel): The Pyomo optimization model.
            t (int): The time interval.

        Returns:
            Constraint: The constraint representing the charging and discharging rule.
        """
        return (
            model.charge_vars[t] + model.discharge_vars[t] <= self.battery.capacity_mwh
        )

    def _soc_update_rule(self, model: pyo.ConcreteModel, t: int):
        """
        Define the state of charge (SOC) update constraint rule for the optimization model.

        Args:
            model (pyo.ConcreteModel): The Pyomo optimization model.
            t (int): The time interval.

        Returns:
            Constraint: The constraint representing the SOC update rule.
        """
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
        """
        Define the energy cycled update constraint rule for the optimization model.

        Args:
            model (pyo.ConcreteModel): The Pyomo optimization model.
            t (int): The time interval.

        Returns:
            Constraint: The constraint representing the energy cycled update rule.
        """
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
        """
        Define the constraints for the optimization model.

        Args:
            model (pyo.ConcreteModel): The Pyomo optimization model.
            num_intervals (int): The number of time intervals.
            max_cycles (float): The maximum number of cycles allowed for the battery.
        """
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
    """
    A solver implementation using the GLPK solver.

    Args:
        log_level (int): The log level for the solver's logger. Defaults to Logger.INFO.

    Attributes:
        logger (Logger): The logger instance for logging solver information.

    """

    def __init__(self, log_level: int = Logger.INFO):
        self.logger = Logger(log_level)

    def solve(self, model: pyo.ConcreteModel, tee: bool = False):
        """
        Solves the optimization model using the GLPK solver.

        Args:
            model (pyo.ConcreteModel): The optimization model to be solved.
            tee (bool): Whether to display solver output. Defaults to False.

        Returns:
            The result of the optimization solver.

        """
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
