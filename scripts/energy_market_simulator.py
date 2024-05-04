from datetime import date, timedelta

import pandas as pd
from tqdm import tqdm

from scripts.battery import Battery
from scripts.prices import IPriceData
from scripts.scheduler import BatteryOptimizationScheduler


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


class EnergyMarketSimulator:
    def __init__(
        self,
        start_date: date,
        end_date: date,
        battery: Battery,
        price_model: IPriceData,
        pnl_calculator: PnLCalculator,
        scheduler: BatteryOptimizationScheduler,
    ):
        assert end_date >= start_date, "End date must be after start date."
        self.start_date = start_date
        self.end_date = end_date
        self.battery = battery
        self.price_model = price_model
        self.pnl_calculator = pnl_calculator
        self.scheduler = scheduler

    def process_daily_schedule(self, schedule_df: pd.DataFrame):
        for _, row in schedule_df.iterrows():
            charge_value = row["Charge"]
            discharge_value = row["Discharge"]
            if charge_value > 0:
                self.battery.charge(charge_value)
            elif discharge_value > 0:
                self.battery.discharge(discharge_value)

    def run_daily_operation(self, prices: list, actual_prices: list) -> tuple:
        schedule_df = self.scheduler.create_schedule(prices)
        self.process_daily_schedule(schedule_df)
        pnl = self.pnl_calculator.calculate(schedule_df, actual_prices)
        return schedule_df, pnl

    def simulate(self) -> list:
        total_pnl = 0
        results = []

        for current_day in tqdm(
            range((self.end_date - self.start_date).days + 1), desc="Processing Days"
        ):
            current_date = self.start_date + timedelta(days=current_day)
            envelope_prices, noisy_prices = self.price_model.get_prices(
                date=current_date
            )

            schedule_df, daily_pnl = self.run_daily_operation(
                envelope_prices, noisy_prices
            )
            total_pnl += daily_pnl
            results.append((current_date, schedule_df, daily_pnl))

        print(f"Total P&L from {self.start_date} to {self.end_date}: {total_pnl}")
        return results
