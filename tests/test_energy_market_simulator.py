import os
import pytest
import sys

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))

from datetime import date
import pandas as pd
import numpy as np
from scripts import EnergyMarketSimulator, Battery  # noqa: E402


@pytest.fixture
def sample_battery():
    return Battery(capacity_mwh=1, initial_soc=0.5)


@pytest.fixture
def sample_simulator(sample_battery):
    start_date = date(2023, 1, 1)
    end_date = date(2023, 1, 2)
    return EnergyMarketSimulator(start_date, end_date, sample_battery)

@pytest.mark.skip
def test_initialization(sample_battery):
    start_date = date(2023, 1, 1)
    end_date = date(2023, 1, 2)
    simulator = EnergyMarketSimulator(start_date, end_date, sample_battery)
    assert simulator.start_date == start_date
    assert simulator.end_date == end_date
    assert simulator.battery == sample_battery

@pytest.mark.skip
def test_calculate_pnl(sample_simulator):
    actions = ["charge" if i % 2 == 0 else "discharge" for i in range(48)]
    values = [0.5 if i % 2 == 0 else 0.4 for i in range(48)]

    mock_schedule_df = pd.DataFrame({"Action": actions, "Value": values})
    mock_actual_prices = [20 if i % 2 == 0 else 25 for i in range(48)]

    pnl = sample_simulator.calculate_pnl(mock_schedule_df, mock_actual_prices)
    # Expected P&L calculation
    expected_pnl = -25.3333
    assert np.isclose(pnl, expected_pnl)

@pytest.mark.skip
def test_process_daily_schedule(sample_simulator):
    actions = ["charge" if i % 2 == 0 else "discharge" for i in range(48)]
    values = [0.5 if i % 2 == 0 else 0.4 for i in range(48)]

    mock_schedule_df = pd.DataFrame({"Action": actions, "Value": values})

    initial_soh = sample_simulator.battery.soh

    sample_simulator.process_daily_schedule(mock_schedule_df)

    # Assuming the battery's charge and discharge methods update the SOC appropriately
    assert sample_simulator.battery.soh != initial_soh

@pytest.mark.skip
def test_run_daily_operation(sample_simulator):
    mock_prices = [20] * 48
    mock_actual_prices = [22] * 48
    schedule_df, pnl = sample_simulator.run_daily_operation(
        mock_prices, mock_actual_prices
    )

    assert isinstance(schedule_df, pd.DataFrame)
    assert len(schedule_df) == 48
    assert "Action" in schedule_df.columns and "Value" in schedule_df.columns
    assert pnl is not None


if __name__ == "__main__":
    pytest.main()
