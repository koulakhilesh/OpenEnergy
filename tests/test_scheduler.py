import os
import pytest
import pandas as pd
import sys
from scripts.battery import Battery  # noqa: E402
from scripts.energy_market_simulator import MarketScheduler  # noqa: E402
import pyomo.environ as pyo

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))


@pytest.fixture
def sample_battery():
    return Battery(capacity_mwh=1, initial_soc=0.5)


@pytest.fixture
def sample_scheduler(sample_battery):
    prices = [20] * 24 + [40] * 24
    return MarketScheduler(sample_battery, prices)


def test_setup_model(sample_scheduler: MarketScheduler):
    num_intervals = 5
    sample_scheduler.setup_model(num_intervals)
    assert isinstance(sample_scheduler.model, pyo.ConcreteModel)
    assert sample_scheduler.model._name == "Battery_Schedule_Optimization"


def test_define_variables(sample_scheduler: MarketScheduler):
    num_intervals = 5
    sample_scheduler.setup_model(num_intervals)
    sample_scheduler.define_variables(num_intervals)

    assert len(sample_scheduler.model.charge_vars) == num_intervals
    assert len(sample_scheduler.model.discharge_vars) == num_intervals
    assert len(sample_scheduler.model.soc_vars) == num_intervals + 1


def test_add_objective_function(sample_scheduler: MarketScheduler):
    num_intervals = 5
    timestep_hours = 0.5
    sample_scheduler.setup_model(num_intervals)
    sample_scheduler.define_variables(num_intervals)
    sample_scheduler.add_objective_function(num_intervals, timestep_hours)
    assert isinstance(sample_scheduler.model.objective, pyo.Objective)


def test_add_constraints(sample_scheduler: MarketScheduler):
    num_intervals = 5
    max_cycles = 100
    sample_scheduler.setup_model(num_intervals)
    sample_scheduler.define_variables(num_intervals)
    sample_scheduler.add_constraints(num_intervals, max_cycles)
    assert len(list(sample_scheduler.model.component_objects(pyo.Var))) > 0


def test_create_schedule(sample_scheduler: MarketScheduler):
    schedule_df = sample_scheduler.create_schedule(tee=True)
    assert isinstance(schedule_df, pd.DataFrame)
    assert not schedule_df.empty


if __name__ == "__main__":
    pytest.main()
