import os
import pytest
import pandas as pd
import sys
import pulp

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts.battery import Battery  # noqa: E402
from scripts.energy_market_simulator import MarketScheduler  # noqa: E402


@pytest.fixture
def sample_battery():
    return Battery(capacity_mwh=1, initial_soc=0.5)


@pytest.fixture
def sample_scheduler(sample_battery):
    prices = [20] * 24 + [40] * 24
    return MarketScheduler(sample_battery, prices)


def test_setup_model(sample_scheduler):
    num_intervals = 5
    model = sample_scheduler.setup_model(num_intervals)
    assert model.name == "Battery_Schedule_Optimization"
    assert model.sense == -1


def test_define_variables(sample_scheduler):
    num_intervals = 5
    vars = sample_scheduler.define_variables(None, num_intervals)
    assert len(vars["charge"]) == num_intervals
    assert len(vars["discharge"]) == num_intervals
    assert len(vars["soc"]) == num_intervals + 1


def test_add_objective_function(sample_scheduler):
    model = pulp.LpProblem()
    vars = {
        "charge": [pulp.LpVariable("charge") for _ in range(5)],
        "discharge": [pulp.LpVariable("discharge") for _ in range(5)],
        "soc": [pulp.LpVariable("soc") for _ in range(6)],
    }
    num_intervals = 5
    timestep_hours = 0.5
    sample_scheduler.add_objective_function(model, vars, num_intervals, timestep_hours)
    assert model.objective is not None


def test_add_constraints(sample_scheduler):
    model = pulp.LpProblem()
    vars = {
        "charge": [pulp.LpVariable("charge") for _ in range(5)],
        "discharge": [pulp.LpVariable("discharge") for _ in range(5)],
        "soc": [pulp.LpVariable("soc") for _ in range(6)],
        "energy_cycled": [pulp.LpVariable("energy_cycled") for _ in range(6)],
    }
    num_intervals = 5
    max_cycles = 100
    sample_scheduler.add_constraints(model, vars, num_intervals, max_cycles)
    assert len(model.constraints) != 0


def test_create_schedule(sample_scheduler):
    schedule_df = sample_scheduler.create_schedule()
    assert isinstance(schedule_df, pd.DataFrame)


if __name__ == "__main__":
    pytest.main()
