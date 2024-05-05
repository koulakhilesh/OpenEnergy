from datetime import date, timedelta

import pandas as pd
from tqdm import tqdm

from scripts.assets import Battery
from scripts.optimizer import BatteryOptimizationScheduler
from scripts.prices import IPriceData

from .pnl_calculator import PnLCalculator
from scripts.shared import Logger


class EnergyMarketSimulator:
    def __init__(
        self,
        start_date: date,
        end_date: date,
        battery: Battery,
        price_model: IPriceData,
        pnl_calculator: PnLCalculator,
        scheduler: BatteryOptimizationScheduler,
        log_level: int = Logger.INFO,

    ):  
        self.logger = Logger(log_level)
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
            if charge_value >= 0:
                self.battery.charge(charge_value)
            elif discharge_value > 0:
                self.battery.discharge(discharge_value)

    def run_daily_operation(self, prices: list, actual_prices: list) -> tuple:
        schedule_df = self.scheduler.create_schedule(prices)
        self.logger.debug(f"Schedule for {self.start_date}: {schedule_df}")
        self.process_daily_schedule(schedule_df)
        pnl = self.pnl_calculator.calculate(schedule_df, actual_prices)
        return schedule_df, pnl

    def simulate(self) -> list:
        total_pnl = 0
        results = []

        for current_day in tqdm(
            range((self.end_date - self.start_date).days + 1), desc="Processing Days", dynamic_ncols=True
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
        self.logger.info(f"Total P&L from {self.start_date} to {self.end_date}: {total_pnl}")
        return results
