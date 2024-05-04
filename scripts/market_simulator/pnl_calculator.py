import pandas as pd

from scripts.assets import Battery


class PnLCalculator:
    def __init__(self, battery: Battery):
        self.battery = battery

    def calculate(
        self,
        schedule_df: pd.DataFrame,
        actual_prices: list,
        timestep_hours: float = 1.0,
    ) -> float:
        pnl = 0
        for i in range(len(actual_prices)):
            charge_value = schedule_df.at[i, "Charge"]
            discharge_value = schedule_df.at[i, "Discharge"]
            action = "charge" if charge_value > 0 else "discharge"
            value = charge_value if charge_value > 0 else discharge_value
            price = actual_prices[i] * timestep_hours

            if action == "charge":
                pnl -= value * price / self.battery.charge_efficiency
            elif action == "discharge":
                pnl += value * price * self.battery.discharge_efficiency
        return pnl
