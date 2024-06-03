import pandas as pd

from scripts.assets import Battery


class PnLCalculator:
    """
    Class to calculate the Profit and Loss (PnL) based on a given schedule and actual prices.

    Args:
        battery (Battery): The battery object used for calculations.

    Attributes:
        battery (Battery): The battery object used for calculations.

    Methods:
        calculate: Calculates the PnL based on the given schedule and actual prices.

    """

    def __init__(self, battery: Battery):
        self.battery = battery

    def calculate(
        self,
        schedule_df: pd.DataFrame,
        actual_prices: list,
        timestep_hours: float = 1.0,
    ) -> float:
        """
        Calculates the Profit and Loss (PnL) based on a given schedule and actual prices.

        Args:
            schedule_df (pd.DataFrame): The schedule dataframe containing charge and discharge values.
            actual_prices (list): The list of actual prices corresponding to each timestep.
            timestep_hours (float, optional): The duration of each timestep in hours. Defaults to 1.0.

        Returns:
            float: The calculated PnL.

        """
        pnl = 0
        for i in range(len(actual_prices)):
            charge_value = schedule_df.at[i, "Charge"]
            discharge_value = schedule_df.at[i, "Discharge"]
            price = actual_prices[i] * timestep_hours

            if charge_value > 0:
                pnl -= charge_value * price / self.battery.charge_efficiency
            elif discharge_value > 0:
                pnl += discharge_value * price * self.battery.discharge_efficiency
            else:
                continue  # Skip this iteration if both charge_value and discharge_value are zero
        return pnl
