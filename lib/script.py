import datetime
import pulp
import random
from tqdm import tqdm


class Battery:
    """Represents a battery with capacity, SOC, and charge/discharge functions considering efficiency."""

    def __init__(self, capacity_mw, charge_efficiency=0.9, discharge_efficiency=0.9):
        self.capacity_mw = capacity_mw
        self.charge_efficiency = charge_efficiency
        self.discharge_efficiency = discharge_efficiency
        self.soc = 0  # State of Charge

    def charge(self, mw):
        """Charge the battery considering efficiency."""
        actual_charge = mw * self.charge_efficiency
        self.soc = min(self.soc + actual_charge, self.capacity_mw)

    def discharge(self, mw):
        """Discharge the battery considering efficiency."""
        actual_discharge = mw * self.discharge_efficiency
        self.soc = max(self.soc - actual_discharge, 0)

    def get_soc(self):
        """Return the current state of charge."""
        return self.soc


class MarketScheduler:
    """Handles scheduling of battery charge/discharge using MILP."""

    def __init__(self, battery, prices):
        self.battery = battery
        self.prices = prices

    def create_schedule(self):
        """
        Create a charging/discharging schedule using MILP.
        """
        # MILP model setup
        model = pulp.LpProblem("Battery_Schedule_Optimization", pulp.LpMaximize)
        charge_vars = [
            pulp.LpVariable(f"charge_{i}", lowBound=0, upBound=self.battery.capacity_mw)
            for i in range(48)
        ]
        discharge_vars = [
            pulp.LpVariable(
                f"discharge_{i}", lowBound=0, upBound=self.battery.capacity_mw
            )
            for i in range(48)
        ]
        soc_vars = [
            pulp.LpVariable(f"soc_{i}", lowBound=0, upBound=self.battery.capacity_mw)
            for i in range(49)
        ]  # Including initial SOC

        # Objective Function
        model += pulp.lpSum(
            [
                discharge_vars[i] * self.prices[i] * self.battery.discharge_efficiency
                - charge_vars[i] * self.prices[i] / self.battery.charge_efficiency
                for i in range(48)
            ]
        )

        # Constraints
        for i in range(48):
            # Battery can either charge or discharge, not both at the same time
            model += charge_vars[i] + discharge_vars[i] <= self.battery.capacity_mw

            # SOC evolution
            if i == 0:
                # Initial SOC is considered here
                model += (
                    soc_vars[i + 1] * self.battery.discharge_efficiency
                    == soc_vars[i] * self.battery.discharge_efficiency
                    + charge_vars[i] * self.battery.charge_efficiency
                    - discharge_vars[i]
                )

            else:
                model += (
                    soc_vars[i + 1] * self.battery.discharge_efficiency
                    == soc_vars[i] * self.battery.discharge_efficiency
                    + charge_vars[i] * self.battery.charge_efficiency
                    - discharge_vars[i]
                )

        # Solve model
        model.solve(pulp.GLPK_CMD(msg=False))

        # Extract schedule
        schedule = [
            "charge" if charge_vars[i].varValue > 0 else "discharge" for i in range(48)
        ]
        return schedule


def load_price_data():
    """
    Load the last day's price data with random values for simulation, for every 30 minutes.
    """
    # Generate a list of random prices for 48 half-hour intervals
    prices = [random.uniform(10, 30) for _ in range(48)]
    return prices


def calculate_pnl(schedule, actual_prices, battery):
    """
    Calculate the profit and loss based on the schedule, actual prices, and battery efficiency.
    """
    pnl = 0
    for action, price in zip(schedule, actual_prices):
        if action == "charge":
            pnl -= price * battery.charge_efficiency
        else:
            pnl += price * battery.discharge_efficiency
    return pnl


def run_daily_operation(prices, actual_prices):
    battery = Battery(1)  # 1 MW battery
    scheduler = MarketScheduler(battery, prices)

    # Create a schedule for the day
    schedule = scheduler.create_schedule()

    # Calculate P&L
    pnl = calculate_pnl(schedule, actual_prices, battery)
    return schedule, pnl


def main():
    # Run the operation for each day of the year 2023
    start_date = datetime.date(2023, 1, 1)
    end_date = datetime.date(2023, 12, 31)

    total_pnl = 0  # Initialize total P&L

    # Using tqdm for the progress bar
    for current_date in tqdm(
        range((end_date - start_date).days + 1), desc="Processing Days"
    ):
        current_date = start_date + datetime.timedelta(days=current_date)
        prices = load_price_data()  # Load forecasted prices
        actual_prices = (
            load_price_data()
        )  # Load actual prices (placeholder, replace with actual data)
        schedule, pnl = run_daily_operation(prices, actual_prices)

        # Add daily P&L to total P&L
        total_pnl += pnl

        # print(f"Date: {current_date}, Schedule: {schedule}, P&L: {pnl}")

    # Print the total P&L after the loop
    print(f"Total P&L from {start_date} to {end_date}: {total_pnl}")


if __name__ == "__main__":
    main()
