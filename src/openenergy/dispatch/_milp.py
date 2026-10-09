"""Shared HiGHS MILP plumbing for dispatch models."""

from __future__ import annotations

from collections.abc import Sequence

import highspy
import numpy as np
import numpy.typing as npt

from openenergy.assets.battery import TOLERANCE
from openenergy.errors import DispatchError, InfeasibleDispatchError

FloatArray = npt.NDArray[np.float64]
# (column indices, coefficients, lower bound, upper bound)
Row = tuple[list[int], list[float], float, float]
INF = highspy.kHighsInf


def validate_horizon(prices: Sequence[float] | FloatArray, step_hours: float) -> FloatArray:
    price = np.asarray(prices, dtype=np.float64)
    if price.ndim != 1:
        raise DispatchError("prices must be one-dimensional")
    if price.size == 0:
        raise DispatchError("prices need at least one interval")
    if not np.isfinite(price).all():
        raise DispatchError("prices must be finite")
    if step_hours <= 0:
        raise DispatchError(f"step_hours must be positive, got {step_hours}")
    return price


def solve_milp(
    cost: FloatArray,
    col_lower: FloatArray,
    col_upper: FloatArray,
    rows: list[Row],
    integer_from: int,
    mip_rel_gap: float,
) -> FloatArray:
    """Maximise ``cost @ x``; columns from ``integer_from`` onwards are integer."""
    lp = highspy.HighsLp()
    lp.num_col_ = cost.size
    lp.num_row_ = len(rows)
    lp.sense_ = highspy.ObjSense.kMaximize
    lp.col_cost_ = cost
    lp.col_lower_ = col_lower
    lp.col_upper_ = col_upper
    lp.row_lower_ = np.array([row[2] for row in rows])
    lp.row_upper_ = np.array([row[3] for row in rows])
    lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
    lp.a_matrix_.num_col_ = cost.size
    lp.a_matrix_.num_row_ = len(rows)
    lp.a_matrix_.start_ = np.cumsum([0] + [len(row[0]) for row in rows], dtype=np.int32)
    lp.a_matrix_.index_ = np.array([i for row in rows for i in row[0]], dtype=np.int32)
    lp.a_matrix_.value_ = np.array([v for row in rows for v in row[1]], dtype=np.float64)
    lp.integrality_ = [
        highspy.HighsVarType.kInteger if i >= integer_from else highspy.HighsVarType.kContinuous
        for i in range(cost.size)
    ]

    solver = highspy.Highs()  # type: ignore[no-untyped-call]  # unannotated upstream stub
    solver.setOptionValue("output_flag", False)
    solver.setOptionValue("mip_rel_gap", mip_rel_gap)
    solver.passModel(lp)
    solver.run()
    status = solver.getModelStatus()
    # All columns are bounded, so "unbounded or infeasible" can only mean infeasible.
    if status in (
        highspy.HighsModelStatus.kInfeasible,
        highspy.HighsModelStatus.kUnboundedOrInfeasible,
    ):
        raise InfeasibleDispatchError("battery cannot meet its SOC limits and end-energy target")
    if status != highspy.HighsModelStatus.kOptimal:
        raise DispatchError(
            f"HiGHS did not find an optimal plan: {solver.modelStatusToString(status)}"
        )
    return np.asarray(solver.getSolution().col_value, dtype=np.float64)


def clean(values: FloatArray, upper: float | FloatArray) -> FloatArray:
    """Clip solver output to [0, upper] and zero out round-off."""
    cleaned = np.clip(values, 0.0, upper)
    cleaned[cleaned < TOLERANCE] = 0.0
    return cleaned
