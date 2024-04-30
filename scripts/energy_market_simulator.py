from datetime import date, timedelta
from tqdm import tqdm
from scripts.battery import Battery
from scripts.scheduler import BatteryOptimizationScheduler
from scripts.prices import SimulatedPriceModel
import pandas as pd


class EnergyMarketSimulator:
    """
    A class representing an energy market simulator.

    Attributes:
    - start_date (date): The start date of the simulation.
    - end_date (date): The end date of the simulation.
    - battery (Battery): The battery used in the simulation.

    Methods:
    - __init__(start_date: date, end_date: date, battery: Battery): Initializes the EnergyMarketSimulator object.
    - calculate_pnl(schedule_df: pd.DataFrame, actual_prices: list, timestep_hours: float ) -> float: Calculates the profit and loss (P&L) based on the schedule and actual prices.
    - process_daily_schedule(schedule_df: pd.DataFrame): Processes the daily schedule by charging or discharging the battery.
    - run_daily_operation(prices: list, actual_prices: list) -> tuple: Runs the daily operation of creating a schedule, processing the schedule, and calculating the P&L.
    - simulate(): Simulates the energy market for the specified period and returns the results.
    """

    def __init__(self, start_date: date, end_date: date, battery: Battery):
        """
        Initializes the EnergyMarketSimulator object.

        Parameters:
        - start_date (date): The start date of the simulation.
        - end_date (date): The end date of the simulation.
        - battery (Battery): The battery used in the simulation.
        """
        assert end_date >= start_date, "End date must be after start date."
        self.start_date = start_date
        self.end_date = end_date
        self.battery = battery

    def calculate_pnl(
        self,
        schedule_df: pd.DataFrame,
        actual_prices: list,
        timestep_hours: float = 1.0,
    ) -> float:
        """
        Calculates the profit and loss (P&L) based on the schedule and actual prices.

        Parameters:
        - schedule_df (pd.DataFrame): The schedule dataframe containing the actions and values.
        - actual_prices (list): The list of actual market prices.
        - timestep_hours (float): The duration of each timestep in hours. Default is 1.0.

        Returns:
        - pnl (float): The calculated profit and loss.
        """
        pnl = 0
        for i in range(len(actual_prices)):
            charge_value = schedule_df.at[i, "Charge"]
            discharge_value = schedule_df.at[i, "Discharge"]
            action = "charge" if charge_value > 0 else "discharge"
            value = charge_value if charge_value > 0 else discharge_value
            price = (
                actual_prices[i] * timestep_hours
            )  # Adjust for timestep duration if prices are per hour

            if action == "charge":
                pnl -= value * price / self.battery.charge_efficiency
            elif action == "discharge":
                pnl += value * price * self.battery.discharge_efficiency
        return pnl

    def process_daily_schedule(self, schedule_df: pd.DataFrame):
        """
        Processes the daily schedule by charging or discharging the battery.

        Parameters:
        - schedule_df (pd.DataFrame): The schedule dataframe containing the actions and values.
        """
        for _, row in schedule_df.iterrows():
            charge_value = row["Charge"]
            discharge_value = row["Discharge"]
            if charge_value > 0:
                self.battery.charge(charge_value)
            elif discharge_value > 0:
                self.battery.discharge(discharge_value)

    def run_daily_operation(self, prices: list, actual_prices: list) -> tuple:
        """
        Runs the daily operation of creating a schedule, processing the schedule, and calculating the profit and loss (P&L).

        Parameters:
        - prices (list): The list of placeholder market prices.
        - actual_prices (list): The list of actual market prices.

        Returns:
        - tuple: A tuple containing the schedule dataframe and the calculated P&L.
        """
        scheduler = BatteryOptimizationScheduler(self.battery, prices)
        schedule_df = scheduler.create_schedule()
        self.process_daily_schedule(schedule_df)
        pnl = self.calculate_pnl(schedule_df, actual_prices)
        return schedule_df, pnl

    def simulate(self, price_mode: str = "simulate") -> list:
        """
        Simulates the energy market for the specified period and returns the results.

        Returns:
        - results (list): A list of tuples containing the date, schedule dataframe, and daily P&L for each day of the simulation.
        """
        total_pnl = 0
        results = []  # Collect daily operation results for analysis

        assert price_mode in ["simulate", "historical"], "Invalid price mode."
        price_model = SimulatedPriceModel()

        for current_day in tqdm(
            range((self.end_date - self.start_date).days + 1), desc="Processing Days"
        ):
            current_date = self.start_date + timedelta(days=current_day)
            envelope_prices, noisy_prices = price_model.get_prices(date=current_date)

            schedule_df, daily_pnl = self.run_daily_operation(
                envelope_prices, noisy_prices
            )
            total_pnl += daily_pnl
            results.append((current_date, schedule_df, daily_pnl))

        print(f"Total P&L from {self.start_date} to {self.end_date}: {total_pnl}")
        return results  # Optionally return the results for further analysis
