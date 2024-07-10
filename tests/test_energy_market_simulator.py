import os
import sys
from datetime import date

import pandas as pd
import pytest

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))

from scripts.assets.battery import Battery
from scripts.market_simulator import EnergyMarketSimulator, PnLCalculator
from scripts.optimizer.scheduler import BatteryOptimizationScheduler
from scripts.prices.interfaces import IPriceData


@pytest.fixture
def battery():
    return Battery(
        capacity_mwh=100,
        initial_soc=0.5,
        charge_efficiency=0.9,
        discharge_efficiency=0.8,
    )


@pytest.fixture
def schedule_df():
    data = {"Charge": [10, 0, 0, 20], "Discharge": [0, 15, 0, 0]}
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
    def __init__(
        self,
        battery=None,
        model_builder=None,
        solver=None,
        model_extractor=None,
    ):
        super().__init__(battery, model_builder, solver, model_extractor)

    def create_schedule(self, prices):
        data = {"Charge": [10, 0, 0, 0], "Discharge": [0, 15, 5, 0]}
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
        scheduler=scheduler,
    )

    results = simulator.simulate()

    # Check that the simulator ran for the correct number of days
    assert len(results) == 2

    # Check the PnL for each day
    for result in results:
        current_date, schedule_df, daily_pnl = result
        expected_pnl = pnl_calculator.calculate(schedule_df, [11, 21, 31, 41])
        assert daily_pnl == pytest.approx(expected_pnl)


def test_energy_market_simulator_single_day(
    battery, pnl_calculator, price_model, scheduler
):
    simulator = EnergyMarketSimulator(
        start_date=date(2022, 1, 1),
        end_date=date(2022, 1, 1),
        battery=battery,
        price_model=price_model,
        pnl_calculator=pnl_calculator,
        scheduler=scheduler,
    )

    results = simulator.simulate()

    # Check that the simulator ran for the correct number of days
    assert len(results) == 1

    # Check the PnL for the day
    current_date, schedule_df, daily_pnl = results[0]
    expected_pnl = pnl_calculator.calculate(schedule_df, [11, 21, 31, 41])
    assert daily_pnl == pytest.approx(expected_pnl)


if __name__ == "__main__":
    pytest.main([__file__])
