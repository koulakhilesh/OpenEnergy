import datetime
import random
from tqdm import tqdm
from .battery import Battery
from .scheduler import MarketScheduler


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
