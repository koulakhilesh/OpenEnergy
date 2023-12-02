from datetime import date, timedelta
from tqdm import tqdm
from .battery import Battery
from .scheduler import MarketScheduler
from .prices import Price
import pandas as pd


class EnergyMarketSimulator:
    def __init__(self, start_date: date, end_date: date, battery: Battery):
        self.start_date = start_date
        self.end_date = end_date
        self.battery = battery

    def calculate_pnl(self, schedule_df: pd.DataFrame, actual_prices: list) -> float:
        pnl = 0
        for i in range(48):
            action = schedule_df.at[i, "Action"]
            value = schedule_df.at[i, "Value"]
            price = actual_prices[i] / 2

            if action == "charge":
                pnl -= value * price / self.battery.charge_efficiency
            elif action == "discharge":
                pnl += value * price * self.battery.discharge_efficiency
        return pnl

    def process_daily_schedule(self, schedule_df: pd.DataFrame):
        """Process the daily schedule to update the battery's state."""
        for action, value in zip(schedule_df["Action"], schedule_df["Value"]):
            if action == "charge":
                self.battery.charge(value)
            elif action == "discharge":
                self.battery.discharge(value)

    def run_daily_operation(self, prices: list, actual_prices: list) -> tuple:
        scheduler = MarketScheduler(self.battery, prices)
        schedule_df = scheduler.create_schedule()
        self.process_daily_schedule(
            schedule_df
        )  # Process the schedule to update the battery
        pnl = self.calculate_pnl(schedule_df, actual_prices)
        return schedule_df, pnl

    def simulate(self):
        total_pnl = 0
        for current_date in tqdm(
            range((self.end_date - self.start_date).days + 1), desc="Processing Days"
        ):
            current_date = self.start_date + timedelta(days=current_date)
            prices = Price.load_placeholder_price_data()
            actual_prices = Price.load_random_price_data()
            schedule_df, pnl = self.run_daily_operation(prices, actual_prices)
            total_pnl += pnl
            print(schedule_df.head())

        print(f"Total P&L from {self.start_date} to {self.end_date}: {total_pnl}")
