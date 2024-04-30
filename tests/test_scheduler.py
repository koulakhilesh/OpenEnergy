import os
import pytest
import pandas as pd
import sys

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts.battery import Battery  # noqa: E402
from scripts.scheduler import (  # noqa: E402
    BatteryOptimizationScheduler,
    PyomoOptimizationModelBuilder,
    GLPKOptimizationSolver,
)


# Sample Battery Fixture
@pytest.fixture
def sample_battery():
    return Battery(
        capacity_mwh=1,
        charge_efficiency=0.9,
        discharge_efficiency=0.9,
        initial_soc=0.5,
        initial_soh=1.0,
    )


# Sample Prices Fixture
@pytest.fixture
def sample_prices():
    return [20] * 12 + [40] * 12  # Example price curve


# Sample Scheduler Fixture
@pytest.fixture
def sample_scheduler(sample_battery, sample_prices):
    model_builder = PyomoOptimizationModelBuilder()
    solver = GLPKOptimizationSolver()
    return BatteryOptimizationScheduler(
        sample_battery, sample_prices, model_builder, solver
    )


def test_create_schedule(sample_scheduler: BatteryOptimizationScheduler, sample_prices):
    schedule_df = sample_scheduler.create_schedule(tee=False)
    assert isinstance(schedule_df, pd.DataFrame)
    assert not schedule_df.empty
    assert len(schedule_df) == len(
        sample_prices
    )  # Ensure schedule length matches number of intervals
    assert "Charge" in schedule_df.columns
    assert "Discharge" in schedule_df.columns
    assert "SOC" in schedule_df.columns


def test_handle_zero_prices(sample_battery):
    prices = [0] * 24  # 24 hours of zero prices
    model_builder = PyomoOptimizationModelBuilder()
    solver = GLPKOptimizationSolver()
    scheduler = BatteryOptimizationScheduler(
        sample_battery, prices, model_builder, solver
    )
    schedule_df = scheduler.create_schedule()
    assert schedule_df["Charge"].sum() == 0
    assert schedule_df["Discharge"].sum() == 0


def test_handle_negative_prices(sample_battery):
    prices = [-5] * 24  # Negative prices for 24 hours
    scheduler = BatteryOptimizationScheduler(sample_battery, prices)
    schedule_df = scheduler.create_schedule()
    assert schedule_df["Charge"].sum() > 0  # Expect some charging


def test_soc_limits(sample_scheduler: BatteryOptimizationScheduler):
    schedule_df = sample_scheduler.create_schedule()
    assert schedule_df["SOC"].min() >= 0.05  # Assuming 0.05 is the minimum SOC
    assert schedule_df["SOC"].max() <= 0.95  # Assuming 0.95 is the maximum SOC


def test_energy_cycled_limit(sample_scheduler: BatteryOptimizationScheduler):
    schedule_df = sample_scheduler.create_schedule()
    total_energy_cycled = schedule_df["Charge"].sum() + schedule_df["Discharge"].sum()
    max_allowed_cycled = (
        sample_scheduler.battery.capacity_mwh * 2 * 5
    )  # Example calculation
    assert total_energy_cycled <= max_allowed_cycled


# TODO: Add more tests for edge cases and additional functionality

if __name__ == "__main__":
    pytest.main()
