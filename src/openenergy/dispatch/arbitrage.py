"""Single-battery energy arbitrage as a mixed-integer linear programme (HiGHS)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import highspy
import numpy as np
import numpy.typing as npt

from openenergy.assets.battery import TOLERANCE, BatterySpec, BatteryState
from openenergy.errors import ConfigError, DispatchError, InfeasibleDispatchError

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class DispatchConfig:
    """Optimisation settings.

    ``end_soc`` is a fraction of usable energy; ``None`` means return to the starting energy.
    ``max_cycles`` caps equivalent full cycles over the horizon.
    """

    end_soc: float | None = None
    degradation_cost: float = 0.0
    max_cycles: float | None = None
    mip_rel_gap: float = 1e-6

    def __post_init__(self) -> None:
        if self.end_soc is not None and not 0 <= self.end_soc <= 1:
            raise ConfigError(f"end_soc must be in [0, 1], got {self.end_soc}")
        if not (math.isfinite(self.degradation_cost) and self.degradation_cost >= 0):
            raise ConfigError(f"degradation_cost must be non-negative, got {self.degradation_cost}")
        if self.max_cycles is not None and not self.max_cycles > 0:
            raise ConfigError(f"max_cycles must be positive, got {self.max_cycles}")
        if not self.mip_rel_gap >= 0:
            raise ConfigError(f"mip_rel_gap must be non-negative, got {self.mip_rel_gap}")


@dataclass(frozen=True)
class DispatchPlan:
    """Optimal schedule in MW per interval and stored energy at each boundary (T+1)."""

    charge_mw: FloatArray
    discharge_mw: FloatArray
    energy_mwh: FloatArray
    expected_revenue: float
    objective: float


def optimise_dispatch(
    spec: BatterySpec,
    state: BatteryState,
    prices: Sequence[float] | FloatArray,
    step_hours: float,
    config: DispatchConfig | None = None,
) -> DispatchPlan:
    """Maximise arbitrage revenue less degradation cost over the given price horizon."""
    config = config or DispatchConfig()
    price = np.asarray(prices, dtype=np.float64)
    if price.ndim != 1:
        raise DispatchError("prices must be one-dimensional")
    if price.size == 0:
        raise DispatchError("prices need at least one interval")
    if not np.isfinite(price).all():
        raise DispatchError("prices must be finite")
    if step_hours <= 0:
        raise DispatchError(f"step_hours must be positive, got {step_hours}")

    n = price.size
    dt = step_hours
    power = spec.power_mw
    lower, upper = spec.energy_bounds(state)
    usable = spec.usable_energy_mwh(state)
    target = state.energy_mwh if config.end_soc is None else config.end_soc * usable
    if target > upper + TOLERANCE:
        raise InfeasibleDispatchError(
            f"end energy target {target:.6f} MWh exceeds maximum {upper:.6f} MWh"
        )

    # Columns: charge c[0:n], discharge d[n:2n], energy e[2n:3n+1], on-charge flag u[3n+1:4n+1].
    c, d, e, u = 0, n, 2 * n, 3 * n + 1
    num_col = 4 * n + 1
    cost = np.zeros(num_col)
    cost[c : c + n] = -(price + config.degradation_cost) * dt
    cost[d : d + n] = (price - config.degradation_cost) * dt

    col_lower = np.zeros(num_col)
    col_upper = np.full(num_col, power, dtype=np.float64)
    col_lower[e : e + n + 1] = lower
    col_upper[e : e + n + 1] = upper
    col_lower[e] = col_upper[e] = state.energy_mwh
    col_lower[e + n] = max(lower, min(target, upper))
    col_upper[u : u + n] = 1.0

    rows: list[tuple[list[int], list[float], float, float]] = []
    for t in range(n):
        rows.append(
            (
                [e + t + 1, e + t, c + t, d + t],
                [1.0, -1.0, -spec.eta_charge * dt, dt / spec.eta_discharge],
                0.0,
                0.0,
            )
        )
        rows.append(([c + t, u + t], [1.0, -power], -highspy.kHighsInf, 0.0))
        rows.append(([d + t, u + t], [1.0, power], -highspy.kHighsInf, power))
    if config.max_cycles is not None:
        throughput_cols = list(range(c, c + n)) + list(range(d, d + n))
        rows.append(
            (
                throughput_cols,
                [dt] * len(throughput_cols),
                -highspy.kHighsInf,
                2 * config.max_cycles * usable,
            )
        )

    solution = _solve(cost, col_lower, col_upper, rows, integer_from=u, config=config)
    charge = _clean(solution[c : c + n], power)
    discharge = _clean(solution[d : d + n], power)
    energy = np.asarray(solution[e : e + n + 1], dtype=np.float64)
    revenue = float(price @ (discharge - charge) * dt)
    throughput = float((charge + discharge).sum() * dt)
    return DispatchPlan(
        charge_mw=charge,
        discharge_mw=discharge,
        energy_mwh=energy,
        expected_revenue=revenue,
        objective=revenue - config.degradation_cost * throughput,
    )


def _solve(
    cost: FloatArray,
    col_lower: FloatArray,
    col_upper: FloatArray,
    rows: list[tuple[list[int], list[float], float, float]],
    integer_from: int,
    config: DispatchConfig,
) -> FloatArray:
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
    solver.setOptionValue("mip_rel_gap", config.mip_rel_gap)
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


def _clean(values: FloatArray, power: float) -> FloatArray:
    cleaned = np.clip(values, 0.0, power)
    cleaned[cleaned < TOLERANCE] = 0.0
    return cleaned
