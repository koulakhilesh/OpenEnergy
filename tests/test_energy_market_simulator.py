import os
import pytest
import sys
from datetime import date
import pandas as pd
import numpy as np

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))

from scripts.energy_market_simulator import EnergyMarketSimulator  # noqa: E402
from scripts.battery import Battery  # noqa: E402


@pytest.fixture
def sample_battery():
    return Battery(capacity_mwh=1, initial_soc=0.5)


@pytest.fixture
def sample_simulator(sample_battery):
    start_date = date(2023, 1, 1)
    end_date = date(2023, 1, 5)
    return EnergyMarketSimulator(start_date, end_date, sample_battery)


def test_initialization(sample_battery):
    start_date = date(2023, 1, 1)
    end_date = date(2023, 1, 2)
    simulator = EnergyMarketSimulator(start_date, end_date, sample_battery)
    assert simulator.start_date == start_date
    assert simulator.end_date == end_date
    assert simulator.battery == sample_battery


def test_calculate_pnl(sample_simulator):
    schedule_df = pd.DataFrame(
        {
            "Interval": [0, 1],
            "Charge": [0.0, 0.405],
            "Discharge": [0.405, 0.0],
            "SOC": [0.50, 0.50],
        }
    )
    actual_prices = [20, 30]
    pnl = sample_simulator.calculate_pnl(schedule_df, actual_prices)
    assert np.isclose(pnl, -6.209999999999998)


def test_process_daily_schedule(sample_simulator, sample_battery):
    schedule_df = pd.DataFrame(
        {
            "Interval": [0, 1],
            "Charge": [0.0, 0.405],
            "Discharge": [0.405, 0.0],
            "SOC": [0.50, 0.50],
        }
    )
    sample_simulator.process_daily_schedule(schedule_df)
    assert sample_battery.soc == 0.5


def test_run_daily_operation(sample_simulator):
    prices = [20, 30]
    actual_prices = [20, 30]
    initial_soh = sample_simulator.battery.soh
    schedule_df, pnl = sample_simulator.run_daily_operation(prices, actual_prices)
    assert isinstance(schedule_df, pd.DataFrame)
    assert pnl == 34.29
    assert sample_simulator.battery.soh != initial_soh


def test_simulate(sample_simulator):
    results = sample_simulator.simulate()
    assert len(results) == 5
    assert isinstance(results[0], tuple)
    assert isinstance(results[0][0], date)
    assert isinstance(results[0][1], pd.DataFrame)
    assert isinstance(results[0][2], float)


if __name__ == "__main__":
    pytest.main()
