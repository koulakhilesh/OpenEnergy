import pulp
import pandas as pd


class MarketScheduler:
    """Handles scheduling of battery charge/discharge using MILP."""

    def __init__(self, battery, prices):
        self.battery = battery
        self.prices = prices

    def create_schedule(self):
        # MILP model setup
        model = pulp.LpProblem("Battery_Schedule_Optimization", pulp.LpMaximize)
        charge_vars = [
            pulp.LpVariable(
                f"charge_{i}", lowBound=0, upBound=self.battery.capacity_mwh
            )
            for i in range(48)
        ]
        discharge_vars = [
            pulp.LpVariable(
                f"discharge_{i}", lowBound=0, upBound=self.battery.capacity_mwh
            )
            for i in range(48)
        ]
        soc_vars = [
            pulp.LpVariable(f"soc_{i}", lowBound=0.05, upBound=0.95) for i in range(49)
        ]  # SOC as a percentage

        # Objective Function: Adjusted for half-hour intervals

        model += pulp.lpSum(
            [
                (
                    discharge_vars[i]
                    * self.prices[i]
                    * self.battery.discharge_efficiency
                    / 2
                )
                - (
                    charge_vars[i]
                    * self.prices[i]
                    / (self.battery.charge_efficiency * 2)
                )
                for i in range(48)
            ]
        )

        # Constraints

        # Initial SOC
        model += soc_vars[0] == self.battery.soc

        for i in range(48):
            # Ensure that only charging or discharging can occur at a time
            model += charge_vars[i] + discharge_vars[i] <= self.battery.capacity_mwh
            # SoC Evolutions
            model += soc_vars[i + 1] == soc_vars[i] + (
                charge_vars[i]
                * (self.battery.charge_efficiency / self.battery.capacity_mwh)
            ) - (
                discharge_vars[i]
                * (self.battery.discharge_efficiency / self.battery.capacity_mwh)
            )

        # Solve model
        model.solve(pulp.GLPK_CMD(msg=False))

        # Extract schedule and values
        schedule_data = []
        for i in range(48):
            charge_value = charge_vars[i].varValue
            discharge_value = discharge_vars[i].varValue
            if charge_value > 0:
                action = "charge"
                value = charge_value
            elif discharge_value > 0:
                action = "discharge"
                value = discharge_value
            else:
                action = "idle"
                value = 0.0
            schedule_data.append({"Interval": i, "Action": action, "Value": value})

        # Convert to DataFrame
        schedule_df = pd.DataFrame(schedule_data)
        return schedule_df
