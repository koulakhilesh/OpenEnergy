import sys
import pytest
import os
from lib import Battery, MarketScheduler, load_price_data, calculate_pnl, run_daily_operation
sys.path.append(os.path.realpath(os.path.dirname(__file__)+"/.."))

def test_battery_charge():
    battery = Battery(1)  # 1 MW capacity
    battery.charge(0.5)  # Charge with 0.5 MW
    assert battery.get_soc() == 0.5 * 0.9  # Considering charge efficiency

def test_battery_discharge():
    battery = Battery(1)
    battery.charge(1)  # Fully charge the battery first
    battery.discharge(0.5)  # Discharge with 0.5 MW
    assert battery.get_soc() == (1 * 0.9 - 0.5 * 0.9)  # Considering discharge efficiency

def test_market_scheduler():
    battery = Battery(1)
    prices = [20 for _ in range(48)]  # Simplified constant price
    scheduler = MarketScheduler(battery, prices)
    schedule = scheduler.create_schedule()
    
    # Test the length of the schedule and a basic characteristic, like not empty
    assert len(schedule) == 48
    assert any(action in schedule for action in ["charge", "discharge"])

def test_calculate_pnl():
    battery = Battery(1)
    schedule = ['charge'] * 24 + ['discharge'] * 24  # Simplified schedule
    prices = [20 for _ in range(48)]  # Simplified constant price
    pnl = calculate_pnl(schedule, prices, battery)
    
    # Test PnL calculation correctness
    expected_pnl = sum([-20 * 0.9 for _ in range(24)]) + sum([20 * 0.9 for _ in range(24)])
    assert pnl == expected_pnl

def test_load_price_data():
    prices = load_price_data()
    # Test if the function returns a list
    assert isinstance(prices, list)
    # Test if the function returns 48 price points (for 48 half-hour intervals)
    assert len(prices) == 48
    # Test if all returned prices are within the expected range
    assert all(10 <= price <= 30 for price in prices)

def test_run_daily_operation():
    prices = [20 for _ in range(48)]  # Simplified constant prices
    actual_prices = [22 for _ in range(48)]  # Simplified constant actual prices

    schedule, pnl = run_daily_operation(prices, actual_prices)

    # Check if schedule is valid
    assert isinstance(schedule, list)
    assert len(schedule) == 48
    assert all(action in ["charge", "discharge"] for action in schedule)

    # Check if P&L is a number
    assert isinstance(pnl, (int, float))



if __name__ == "__main__":
    pytest.main()