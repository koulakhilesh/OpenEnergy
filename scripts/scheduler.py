from typing import List
import pandas as pd
from .battery import Battery
import pyomo.environ as pyo
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class MarketScheduler:
    """Handles scheduling of battery charge/discharge using MILP.

    Attributes:
        battery (Battery): The battery object.
        prices (List[float]): The list of prices for each interval.
    """

    def __init__(self, battery: Battery, prices: List[float], model=None):
        self.battery = battery
        self.prices = prices
        self.model = model

    def setup_model(self, num_intervals):
        """Sets up the PyOMO model for optimization."""
        self.model = pyo.ConcreteModel(name="Battery_Schedule_Optimization")
        self.model.num_intervals = num_intervals

    def define_variables(self, num_intervals):
        """Defines the PyOMO variables for charging, discharging, and SOC."""

        self.model.charge_vars = pyo.Var(
            range(num_intervals),
            domain=pyo.NonNegativeReals,
            bounds=(0, self.battery.capacity_mwh),
            name="Charge",
        )
        self.model.discharge_vars = pyo.Var(
            range(num_intervals),
            domain=pyo.NonNegativeReals,
            bounds=(0, self.battery.capacity_mwh),
            name="Discharge",
        )
        self.model.soc_vars = pyo.Var(
            range(num_intervals + 1),
            domain=pyo.NonNegativeReals,
            bounds=(0.05, 0.95),
            name="SOC",
        )
        self.model.energy_cycled_vars = pyo.Var(
            range(num_intervals + 1), domain=pyo.NonNegativeReals, name="EnergyCycled"
        )

    def add_objective_function(
        self,
        num_intervals: int,
        timestep_hours: float,
    ):
        """Adds the objective function to the PyOMO model."""

        # Objective expression
        objective_expr = sum(
            (
                self.model.discharge_vars[i]
                * self.prices[i]
                * self.battery.discharge_efficiency
                / timestep_hours
            )
            - (
                self.model.charge_vars[i]
                * self.prices[i]
                / (self.battery.charge_efficiency * timestep_hours)
            )
            for i in range(num_intervals)
        )

        self.model.objective = pyo.Objective(expr=objective_expr, sense=pyo.maximize)

    def add_constraints(self, num_intervals: int, max_cycles: float):
        """Adds constraints to the PyOMO model."""
        self.model.initial_soc_constraint = pyo.Constraint(
            expr=self.model.soc_vars[0] == self.battery.soc
        )
        self.model.initial_energy_cycled_constraint = pyo.Constraint(
            expr=self.model.energy_cycled_vars[0] == 0
        )

        def charging_discharging_rule(model, i):
            return (
                model.charge_vars[i] + model.discharge_vars[i]
                <= self.battery.capacity_mwh
            )

        self.model.charging_discharging_constraint = pyo.Constraint(
            range(num_intervals), rule=charging_discharging_rule
        )

        def soc_update_rule(model, i):
            return model.soc_vars[i + 1] == model.soc_vars[i] + (
                model.charge_vars[i]
                * (self.battery.charge_efficiency / self.battery.capacity_mwh)
            ) - (
                model.discharge_vars[i]
                * (1 / self.battery.discharge_efficiency / self.battery.capacity_mwh)
            )

        self.model.soc_update_constraint = pyo.Constraint(
            range(num_intervals), rule=soc_update_rule
        )

        def energy_cycled_update_rule(model, i):
            return model.energy_cycled_vars[i + 1] == model.energy_cycled_vars[
                i
            ] + model.charge_vars[i] * (
                self.battery.charge_efficiency
            ) + model.discharge_vars[i] * (1 / self.battery.discharge_efficiency)

        self.model.energy_cycled_update_constraint = pyo.Constraint(
            range(num_intervals), rule=energy_cycled_update_rule
        )

        self.model.max_cycles_constraint = pyo.Constraint(
            expr=self.model.energy_cycled_vars[num_intervals]
            <= max_cycles * self.battery.capacity_mwh * 2
        )

    def solve_model(self, tee=False):
        """Solves the LP model using PyOMO."""
        solver = pyo.SolverFactory("glpk")
        result = solver.solve(self.model, tee=tee)

        # Check if the solution is optimal
        if (
            result.solver.status == "ok"
            and result.solver.termination_condition == "optimal"
        ):
            logging.info("Solution is optimal.")
        elif result.solver.termination_condition in [
            "infeasible",
            "infeasibleOrUnbounded",
        ]:
            logging.warning("Solution is infeasible. Review model constraints.")
        elif result.solver.termination_condition == "unbounded":
            logging.warning(
                "Solution is unbounded. Review model objective and constraints."
            )
        elif result.solver.termination_condition == "maxIterations":
            logging.warning("Maximum iterations reached. Solution may not be optimal.")
        else:
            logging.error(
                f"Unexpected solver status encountered: {result.solver.status}, {result.solver.termination_condition}"
            )

    def _extract_schedule(self, num_intervals):
        """Extracts the charging/discharging schedule from the solved PyOMO model."""
        schedule_data = [
            {
                "Interval": i,
                "Action": "charge"
                if pyo.value(self.model.charge_vars[i]) > 0
                else "discharge"
                if pyo.value(self.model.discharge_vars[i]) > 0
                else "idle",
                "Value": max(
                    pyo.value(self.model.charge_vars[i]),
                    pyo.value(self.model.discharge_vars[i]),
                ),
            }
            for i in range(num_intervals)
        ]
        return pd.DataFrame(schedule_data)

    def create_schedule(self, tee=False):
        """Main method to create a charge/discharge schedule for the battery using PyOMO."""
        num_intervals = len(self.prices)
        timestep_hours = 0.5
        max_cycles = 5

        self.setup_model(num_intervals)
        self.define_variables(num_intervals)
        self.add_objective_function(num_intervals, timestep_hours)
        self.add_constraints(num_intervals, max_cycles)
        self.solve_model(tee)

        return self._extract_schedule(num_intervals)
