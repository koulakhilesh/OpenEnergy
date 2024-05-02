import os
import pytest
import sys
from datetime import date
import pandas as pd
import numpy as np

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))

from scripts.battery import Battery  # noqa: E402
from scripts.energy_market_simulator import EnergyMarketSimulator, PnLCalculator  # noqa: E402
from scripts.prices import IPriceData  # noqa: E402
from scripts.scheduler import BatteryOptimizationScheduler  # noqa: E402



@pytest.fixture
def battery():
    return Battery(capacity_mwh=100, initial_soc=0.5, charge_efficiency=0.9, discharge_efficiency=0.8)

@pytest.fixture
def schedule_df():
    data = {
        'Charge': [10, 0, 0, 20],
        'Discharge': [0, 15, 0, 0]
    }
    return pd.DataFrame(data)

@pytest.fixture
def actual_prices():
    return [5, 10, 15, 20]

def test_pnl_calculator(battery, schedule_df, actual_prices):
    pnl_calculator = PnLCalculator(battery)
    pnl = pnl_calculator.calculate(schedule_df, actual_prices)

    # Calculate expected PnL manually
    expected_pnl = -10 * 5 / 0.9 + 15 * 10 * 0.8 - 20 * 20 / 0.9

    assert pnl == pytest.approx(expected_pnl)

class MockPriceModel(IPriceData):
    def get_prices(self, date):
        return [10, 20, 30, 40], [11, 21, 31, 41]

class MockScheduler(BatteryOptimizationScheduler):
    def __init__(self, battery=None, prices=None):
        super().__init__(battery, prices)

    def create_schedule(self, prices):
        data = {
            'Charge': [10, 0, 0, 20],
            'Discharge': [0, 15, 0, 0]
        }
        return pd.DataFrame(data)

@pytest.fixture
def pnl_calculator(battery):
    return PnLCalculator(battery)    

@pytest.fixture
def price_model():
    return MockPriceModel()

@pytest.fixture
def scheduler():
    return MockScheduler()

def test_energy_market_simulator(battery, pnl_calculator, price_model, scheduler):
    simulator = EnergyMarketSimulator(
        start_date=date(2022, 1, 1),
        end_date=date(2022, 1, 2),
        battery=battery,
        price_model=price_model,
        pnl_calculator=pnl_calculator,
        scheduler=scheduler
    )

    results = simulator.simulate()

    # Check that the simulator ran for the correct number of days
    assert len(results) == 2

    # Check the PnL for each day
    for result in results:
        current_date, schedule_df, daily_pnl = result
        expected_pnl = pnl_calculator.calculate(schedule_df, [11, 21, 31, 41])
        assert daily_pnl == pytest.approx(expected_pnl)

def test_energy_market_simulator_single_day(battery, pnl_calculator, price_model, scheduler):
    simulator = EnergyMarketSimulator(
        start_date=date(2022, 1, 1),
        end_date=date(2022, 1, 1),
        battery=battery,
        price_model=price_model,
        pnl_calculator=pnl_calculator,
        scheduler=scheduler
    )

    results = simulator.simulate()

    # Check that the simulator ran for the correct number of days
    assert len(results) == 1

    # Check the PnL for the day
    current_date, schedule_df, daily_pnl = results[0]
    expected_pnl = pnl_calculator.calculate(schedule_df, [11, 21, 31, 41])
    assert daily_pnl == pytest.approx(expected_pnl)

# @pytest.fixture
# def sample_battery():
#     return Battery(capacity_mwh=1, initial_soc=0.5)


# @pytest.fixture
# def sample_simulator(sample_battery):
#     start_date = date(2023, 1, 1)
#     end_date = date(2023, 1, 5)
#     return EnergyMarketSimulator(start_date, end_date, sample_battery)


# def test_initialization(sample_battery):
#     start_date = date(2023, 1, 1)
#     end_date = date(2023, 1, 2)
#     simulator = EnergyMarketSimulator(start_date, end_date, sample_battery)
#     assert simulator.start_date == start_date
#     assert simulator.end_date == end_date
#     assert simulator.battery == sample_battery


# def test_calculate_pnl(sample_simulator):
#     schedule_df = pd.DataFrame(
#         {
#             "Interval": [0, 1],
#             "Charge": [0.0, 0.405],
#             "Discharge": [0.405, 0.0],
#             "SOC": [0.50, 0.50],
#         }
#     )
#     actual_prices = [20, 30]
#     pnl = sample_simulator.calculate_pnl(schedule_df, actual_prices)
#     assert np.isclose(pnl, -6.209999999999998)


# def test_process_daily_schedule(sample_simulator, sample_battery):
#     schedule_df = pd.DataFrame(
#         {
#             "Interval": [0, 1],
#             "Charge": [0.0, 0.405],
#             "Discharge": [0.405, 0.0],
#             "SOC": [0.50, 0.50],
#         }
#     )
#     sample_simulator.process_daily_schedule(schedule_df)
#     assert sample_battery.soc == 0.5


# def test_run_daily_operation(sample_simulator):
#     prices = [20, 30]
#     actual_prices = [20, 30]
#     initial_soh = sample_simulator.battery.soh
#     schedule_df, pnl = sample_simulator.run_daily_operation(prices, actual_prices)
#     assert isinstance(schedule_df, pd.DataFrame)
#     assert pnl == 34.29
#     assert sample_simulator.battery.soh != initial_soh


# def test_simulate(sample_simulator):
#     results = sample_simulator.simulate()
#     assert len(results) == 5
#     assert isinstance(results[0], tuple)
#     assert isinstance(results[0][0], date)
#     assert isinstance(results[0][1], pd.DataFrame)
#     assert isinstance(results[0][2], float)


if __name__ == "__main__":
    pytest.main()
