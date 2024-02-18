from typing import List
import pulp
import pandas as pd
from .battery import Battery


class MarketScheduler:
    """Handles scheduling of battery charge/discharge using MILP.

    Attributes:
        battery (Battery): The battery object.
        prices (List[float]): The list of prices for each interval.
    """

    def __init__(self, battery: Battery, prices: List[float]):
        self.battery = battery
        self.prices = prices

    def setup_model(self, num_intervals: int) -> pulp.LpProblem:
        """Sets up the LP model for optimization."""
        model = pulp.LpProblem("Battery_Schedule_Optimization", pulp.LpMaximize)
        return model

    def define_variables(self, model: pulp.LpProblem, num_intervals: int) -> dict:
        """Defines the LP variables for charging, discharging, and SOC."""
        charge_vars = [
            pulp.LpVariable(
                f"charge_{i}", lowBound=0, upBound=self.battery.capacity_mwh
            )
            for i in range(num_intervals)
        ]
        discharge_vars = [
            pulp.LpVariable(
                f"discharge_{i}", lowBound=0, upBound=self.battery.capacity_mwh
            )
            for i in range(num_intervals)
        ]
        soc_vars = [
            pulp.LpVariable(f"soc_{i}", lowBound=0.05, upBound=0.95)
            for i in range(num_intervals + 1)
        ]
        energy_cycled_vars = [
            pulp.LpVariable(f"cycle_{i}", lowBound=0) for i in range(num_intervals + 1)
        ]

        return {
            "charge": charge_vars,
            "discharge": discharge_vars,
            "soc": soc_vars,
            "energy_cycled": energy_cycled_vars,
        }

    def add_objective_function(
        self,
        model: pulp.LpProblem,
        vars: dict,
        num_intervals: int,
        timestep_hours: float,
    ):
        """Adds the objective function to the model."""
        model += pulp.lpSum(
            [
                (
                    vars["discharge"][i]
                    * self.prices[i]
                    * self.battery.discharge_efficiency
                    / timestep_hours
                )
                - (
                    vars["charge"][i]
                    * self.prices[i]
                    / (self.battery.charge_efficiency * timestep_hours)
                )
                for i in range(num_intervals)
            ]
        )

    def add_constraints(
        self,
        model: pulp.LpProblem,
        vars: dict,
        num_intervals: int,
        max_cycles: float,
    ):
        """Adds constraints to the model."""
        model += vars["soc"][0] == self.battery.soc
        model += vars["energy_cycled"][0] == 0

        for i in range(num_intervals):
            model += (
                vars["charge"][i] + vars["discharge"][i] <= self.battery.capacity_mwh
            )
            model += vars["soc"][i + 1] == vars["soc"][i] + (
                vars["charge"][i]
                * (self.battery.charge_efficiency / self.battery.capacity_mwh)
            ) - (
                vars["discharge"][i]
                * (1 / self.battery.discharge_efficiency / self.battery.capacity_mwh)
            )
            model += vars["energy_cycled"][i + 1] == vars["energy_cycled"][i] + vars[
                "charge"
            ][i] * (self.battery.charge_efficiency) + vars["discharge"][i] * (
                1 / self.battery.discharge_efficiency
            )

        model += (
            vars["energy_cycled"][num_intervals]
            <= max_cycles * self.battery.capacity_mwh * 2
        )

    def solve_model(self, model: pulp.LpProblem) -> None:
        """Solves the LP model."""
        result_status = model.solve()
        # Check if the solution is optimal
        if result_status == pulp.LpStatusOptimal:
            print("Solution is optimal.")
        elif result_status in [pulp.LpStatusNotSolved, pulp.LpStatusUndefined]:
            # Handle sub-optimal or undefined solutions
            print("Solution is sub-optimal or undefined. Review model constraints and objective.")
        elif result_status == pulp.LpStatusInfeasible:
            print("Solution is infeasible. Review model constraints.")
        elif result_status == pulp.LpStatusUnbounded:
            print("Solution is unbounded. Review model objective and constraints.")
        else:
            print("Unexpected solver status encountered.")

    def _extract_schedule(self, vars: dict, num_intervals: int) -> pd.DataFrame:
        """Extracts the charging/discharging schedule from the solved model."""
        schedule_data = [
            {
                "Interval": i,
                "Action": "charge"
                if vars["charge"][i].varValue > 0
                else "discharge"
                if vars["discharge"][i].varValue > 0
                else "idle",
                "Value": max(vars["charge"][i].varValue, vars["discharge"][i].varValue),
            }
            for i in range(num_intervals)
        ]
        return pd.DataFrame(schedule_data)

    def create_schedule(self) -> pd.DataFrame:
        """Main method to create a charge/discharge schedule for the battery."""
        num_intervals = len(self.prices)
        timestep_hours = 0.5
        max_cycles = 5

        model = self.setup_model(num_intervals)
        vars = self.define_variables(model, num_intervals)
        self.add_objective_function(model, vars, num_intervals, timestep_hours)
        self.add_constraints(model, vars, num_intervals, max_cycles)
        self.solve_model(model)

        return self._extract_schedule(vars, num_intervals)
