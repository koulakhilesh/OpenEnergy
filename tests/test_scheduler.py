import os
import pytest
import pandas as pd
import sys
import pyomo.environ as pyo
from unittest import mock

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts.battery import Battery  # noqa: E402
from scripts.scheduler import (  # noqa: E402
    BatteryOptimizationScheduler,
    PyomoModelExtractor,
    PyomoOptimizationModelBuilder,
    GLPKOptimizationSolver,
)


def test_define_time_intervals():
    # Arrange
    builder = PyomoOptimizationModelBuilder()
    model = pyo.ConcreteModel()
    num_intervals = 10

    # Act
    builder.define_time_intervals(model, num_intervals)

    # Assert
    assert len(model.T) == num_intervals


def test_define_variables():
    # Arrange
    builder = PyomoOptimizationModelBuilder()
    model = pyo.ConcreteModel()
    builder.battery = Battery(
        capacity_mwh=1.0,
        charge_efficiency=0.9,
        discharge_efficiency=0.9,
        initial_soc=0.5,
    )
    num_intervals = 10

    # Act
    builder.define_time_intervals(model, num_intervals)
    builder.define_variables(model)

    # Assert
    assert all(
        isinstance(var, pyo.Var)
        for var in [
            model.charge_vars,
            model.discharge_vars,
            model.soc_vars,
            model.energy_cycled_vars,
        ]
    )


def test_define_objective_function():
    # Arrange
    builder = PyomoOptimizationModelBuilder()
    model = pyo.ConcreteModel()
    builder.battery = Battery(
        capacity_mwh=1.0,
        charge_efficiency=0.9,
        discharge_efficiency=0.9,
        initial_soc=0.5,
    )
    builder.prices = [10.0 for _ in range(10)]
    builder.timestep_hours = 1.0
    builder.define_time_intervals(model, 10)
    builder.define_variables(model)

    # Act
    builder.define_objective_function(model)

    # Assert
    assert isinstance(model.objective, pyo.Objective)


def test_define_constraints():
    # Arrange
    builder = PyomoOptimizationModelBuilder()
    model = pyo.ConcreteModel()
    builder.battery = Battery(
        capacity_mwh=1.0,
        charge_efficiency=0.9,
        discharge_efficiency=0.9,
        initial_soc=0.5,
    )
    builder.prices = [10.0 for _ in range(10)]
    builder.timestep_hours = 1.0
    builder.define_time_intervals(model, 10)
    builder.define_variables(model)
    max_cycles = 5.0

    # Act
    builder.define_constraints(model, 10, max_cycles)

    # Assert
    assert all(
        isinstance(constraint, pyo.Constraint)
        for constraint in [
            model.initial_soc_constraint,
            model.charging_discharging_constraint,
            model.soc_update_constraint,
            model.energy_cycled_update_constraint,
            model.max_cycles_constraint,
        ]
    )


@pytest.mark.parametrize(
    "num_intervals,prices,capacity_mwh,charge_efficiency,discharge_efficiency,initial_soc,timestep_hours,max_cycles",
    [
        (1, [10.0], 1.0, 0.9, 0.9, 0.5, 1.0, 5.0),  # Single time interval
        (10, [10.0] * 10, 1.0, 0.9, 0.9, 0.5, 1.0, 0.0),  # Zero max cycles
    ],
)
def test_build_model(
    num_intervals,
    prices,
    capacity_mwh,
    charge_efficiency,
    discharge_efficiency,
    initial_soc,
    timestep_hours,
    max_cycles,
):
    # Arrange
    builder = PyomoOptimizationModelBuilder()
    battery = Battery(
        capacity_mwh=capacity_mwh,
        charge_efficiency=charge_efficiency,
        discharge_efficiency=discharge_efficiency,
        initial_soc=initial_soc,
    )

    # Act
    model = builder.build_model(
        num_intervals, prices, battery, timestep_hours, max_cycles
    )

    # Assert
    assert isinstance(model, pyo.ConcreteModel)
    assert len(model.T) == num_intervals
    assert all(
        isinstance(var, pyo.Var)
        for var in [
            model.charge_vars,
            model.discharge_vars,
            model.soc_vars,
            model.energy_cycled_vars,
        ]
    )
    assert isinstance(model.objective, pyo.Objective)
    assert all(
        isinstance(constraint, pyo.Constraint)
        for constraint in [
            model.initial_soc_constraint,
            model.charging_discharging_constraint,
            model.soc_update_constraint,
            model.energy_cycled_update_constraint,
            model.max_cycles_constraint,
        ]
    )


@pytest.mark.parametrize(
    "status,termination_condition,expected_log",
    [
        (pyo.SolverStatus.ok, pyo.TerminationCondition.optimal, "Solution is optimal."),
        (
            pyo.SolverStatus.warning,
            pyo.TerminationCondition.infeasible,
            "Solution is infeasible. Review model constraints.",
        ),
        (
            pyo.SolverStatus.warning,
            pyo.TerminationCondition.infeasibleOrUnbounded,
            "Solution is infeasible. Review model constraints.",
        ),
        (
            pyo.SolverStatus.warning,
            pyo.TerminationCondition.unbounded,
            "Solution is unbounded. Review model objective and constraints.",
        ),
        (
            pyo.SolverStatus.warning,
            pyo.TerminationCondition.maxIterations,
            "Maximum iterations reached. Solution may not be optimal.",
        ),
        (
            pyo.SolverStatus.error,
            pyo.TerminationCondition.unknown,
            "Unexpected solver status encountered: error, unknown",
        ),
    ],
)
def test_solve_logs_correct_message(status, termination_condition, expected_log):
    # Arrange
    solver = GLPKOptimizationSolver()
    model = pyo.ConcreteModel()

    result = mock.Mock()
    result.solver.status = status
    result.solver.termination_condition = termination_condition

    with mock.patch("pyomo.environ.SolverFactory") as mock_solver_factory, mock.patch(
        "logging.info"
    ) as mock_info, mock.patch("logging.warning") as mock_warning, mock.patch(
        "logging.error"
    ) as mock_error:
        mock_solver_factory.return_value.solve.return_value = result

        # Act
        solver.solve(model)

        # Assert
        if (
            status == pyo.SolverStatus.ok
            and termination_condition == pyo.TerminationCondition.optimal
        ):
            mock_info.assert_called_once_with(expected_log)
        elif status == pyo.SolverStatus.warning and termination_condition in [
            pyo.TerminationCondition.infeasible,
            pyo.TerminationCondition.infeasibleOrUnbounded,
            pyo.TerminationCondition.unbounded,
            pyo.TerminationCondition.maxIterations,
        ]:
            mock_warning.assert_called_once_with(expected_log)
        else:
            mock_error.assert_called_once_with(expected_log)


def test_extract_schedule():
    # Arrange
    extractor = PyomoModelExtractor()
    model = pyo.ConcreteModel()
    num_intervals = 10
    model.T = pyo.RangeSet(0, num_intervals - 1)
    model.charge_vars = pyo.Var(model.T, initialize=1.0)
    model.discharge_vars = pyo.Var(model.T, initialize=2.0)
    model.soc_vars = pyo.Var(model.T, initialize=3.0)

    expected_schedule = pd.DataFrame(
        {
            "Interval": range(num_intervals),
            "Charge": [1.0] * num_intervals,
            "Discharge": [2.0] * num_intervals,
            "SOC": [3.0] * num_intervals,
        }
    )

    # Act
    schedule = extractor.extract_schedule(model, num_intervals)

    # Assert
    pd.testing.assert_frame_equal(schedule, expected_schedule)


def test_create_schedule():
    # Arrange
    battery = Battery(
        capacity_mwh=1.0,
        charge_efficiency=0.9,
        discharge_efficiency=0.9,
        initial_soc=0.5,
    )
    prices = [10.0 for _ in range(10)]
    model_builder = mock.Mock()
    solver = mock.Mock()
    model_extractor = mock.Mock()
    scheduler = BatteryOptimizationScheduler(
        battery, model_builder, solver, model_extractor
    )

    model = pyo.ConcreteModel()
    model_builder.build_model.return_value = model

    result = mock.Mock()
    result.solver.status = pyo.SolverStatus.ok
    result.solver.termination_condition = pyo.TerminationCondition.optimal
    solver.solve.return_value = result

    expected_schedule = mock.Mock()
    model_extractor.extract_schedule.return_value = expected_schedule

    # Act
    schedule = scheduler.create_schedule(prices=prices)

    # Assert
    model_builder.build_model.assert_called_once()
    solver.solve.assert_called_once_with(model, False)
    model_extractor.extract_schedule.assert_called_once_with(model, len(prices))
    assert schedule == expected_schedule


def test_create_schedule_raises_exception_on_failed_optimization():
    # Arrange
    battery = Battery(
        capacity_mwh=1.0,
        charge_efficiency=0.9,
        discharge_efficiency=0.9,
        initial_soc=0.5,
    )
    model_builder = mock.Mock()
    solver = mock.Mock()
    model_extractor = mock.Mock()
    scheduler = BatteryOptimizationScheduler(
        battery, model_builder, solver, model_extractor
    )

    model = mock.Mock()
    model_builder.build_model.return_value = model

    result = mock.Mock()
    result.solver.status = pyo.SolverStatus.warning
    result.solver.termination_condition = pyo.TerminationCondition.infeasible
    solver.solve.return_value = result

    prices = [10.0] * 10

    # Act and Assert
    with pytest.raises(
        Exception,
        match="Optimization failed with status: warning, condition: infeasible",
    ):
        scheduler.create_schedule(prices)


if __name__ == "__main__":
    pytest.main()
