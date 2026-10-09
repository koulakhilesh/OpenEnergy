"""A renewable plant and a battery behind one grid connection."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from openenergy.assets.battery import BatterySpec, BatteryState
from openenergy.dispatch._milp import INF, FloatArray, Row, clean, solve_milp, validate_horizon
from openenergy.dispatch.arbitrage import DispatchConfig, energy_window
from openenergy.errors import ConfigError, DispatchError


@dataclass(frozen=True)
class GridConnection:
    """Connection limits in MW; ``premium_per_mwh`` is paid on renewable output delivered.

    ``import_limit_mw`` defaults to the export limit; set it to 0 to forbid grid charging.
    """

    export_limit_mw: float
    import_limit_mw: float | None = None
    premium_per_mwh: float = 0.0

    def __post_init__(self) -> None:
        if not (math.isfinite(self.export_limit_mw) and self.export_limit_mw >= 0):
            raise ConfigError(f"export_limit_mw must be non-negative, got {self.export_limit_mw}")
        if self.import_limit_mw is None:
            object.__setattr__(self, "import_limit_mw", self.export_limit_mw)
        elif not (math.isfinite(self.import_limit_mw) and self.import_limit_mw >= 0):
            raise ConfigError(f"import_limit_mw must be non-negative, got {self.import_limit_mw}")
        if not math.isfinite(self.premium_per_mwh):
            raise ConfigError(f"premium_per_mwh must be finite, got {self.premium_per_mwh}")

    @property
    def import_mw(self) -> float:
        return self.export_limit_mw if self.import_limit_mw is None else self.import_limit_mw


@dataclass(frozen=True)
class ColocatedPlan:
    """Flows in MW per interval; ``export_mw`` is net (negative when importing)."""

    plant_to_grid_mw: FloatArray
    plant_to_battery_mw: FloatArray
    curtailed_mw: FloatArray
    grid_to_battery_mw: FloatArray
    charge_mw: FloatArray
    discharge_mw: FloatArray
    export_mw: FloatArray
    energy_mwh: FloatArray
    expected_revenue: float
    expected_premium: float
    objective: float


def optimise_colocated(
    spec: BatterySpec,
    state: BatteryState,
    available_mw: Sequence[float] | FloatArray,
    prices: Sequence[float] | FloatArray,
    step_hours: float,
    grid: GridConnection,
    config: DispatchConfig | None = None,
) -> ColocatedPlan:
    """Maximise market revenue plus premium less degradation cost for plant and battery."""
    config = config or DispatchConfig()
    price = validate_horizon(prices, step_hours)
    available = _available(available_mw, price.size)
    n, dt, power = price.size, step_hours, spec.power_mw
    lower, upper, target = energy_window(spec, state, config)
    premium, kappa = grid.premium_per_mwh, config.degradation_cost

    # Columns: plant->grid y, plant->battery s, curtailed k, grid->battery m, discharge d,
    # energy e (n+1), charging flag u.
    y, s, k, m, d, e = 0, n, 2 * n, 3 * n, 4 * n, 5 * n
    u = 6 * n + 1
    num_col = 7 * n + 1
    cost = np.zeros(num_col)
    cost[y : y + n] = (price + premium) * dt
    cost[s : s + n] = (premium - kappa) * dt
    cost[m : m + n] = -(price + kappa) * dt
    cost[d : d + n] = (price - kappa) * dt

    col_lower = np.zeros(num_col)
    col_upper = np.zeros(num_col)
    for start in (y, s, k):
        col_upper[start : start + n] = available
    col_upper[m : m + n] = min(grid.import_mw, power)
    col_upper[d : d + n] = power
    col_lower[e : e + n + 1] = lower
    col_upper[e : e + n + 1] = upper
    col_lower[e] = col_upper[e] = state.energy_mwh
    col_lower[e + n] = target
    col_upper[u : u + n] = 1.0

    eta_c, eta_d = spec.eta_charge, spec.eta_discharge
    rows: list[Row] = []
    for t in range(n):
        rows.append(([y + t, s + t, k + t], [1.0, 1.0, 1.0], available[t], available[t]))
        rows.append(
            (
                [e + t + 1, e + t, s + t, m + t, d + t],
                [1.0, -1.0, -eta_c * dt, -eta_c * dt, dt / eta_d],
                0.0,
                0.0,
            )
        )
        rows.append(([s + t, m + t, u + t], [1.0, 1.0, -power], -INF, 0.0))
        rows.append(([d + t, u + t], [1.0, power], -INF, power))
        rows.append(([y + t, d + t, m + t], [1.0, 1.0, -1.0], -INF, grid.export_limit_mw))
    if config.max_cycles is not None:
        cols = [*range(s, s + n), *range(m, m + n), *range(d, d + n)]
        cap = 2 * config.max_cycles * spec.usable_energy_mwh(state)
        rows.append((cols, [dt] * len(cols), -INF, cap))

    x = solve_milp(cost, col_lower, col_upper, rows, u, config.mip_rel_gap)
    to_grid = clean(x[y : y + n], available)
    to_battery = clean(x[s : s + n], available)
    from_grid = clean(x[m : m + n], power)
    # Exporting and importing in the same interval nets to routing plant output into the battery.
    overlap = np.minimum(to_grid, from_grid)
    to_grid, from_grid, to_battery = to_grid - overlap, from_grid - overlap, to_battery + overlap
    discharge = clean(x[d : d + n], power)
    return _plan(
        price,
        dt,
        premium,
        kappa,
        to_grid=to_grid,
        to_battery=to_battery,
        curtailed=np.clip(available - to_grid - to_battery, 0.0, None),
        from_grid=from_grid,
        discharge=discharge,
        energy=np.asarray(x[e : e + n + 1], dtype=np.float64),
    )


def dispatch_plant(
    available_mw: Sequence[float] | FloatArray,
    prices: Sequence[float] | FloatArray,
    step_hours: float,
    grid: GridConnection,
) -> ColocatedPlan:
    """A plant on its own: export up to the limit unless price plus premium is negative."""
    price = validate_horizon(prices, step_hours)
    available = _available(available_mw, price.size)
    worth_selling = price + grid.premium_per_mwh >= 0
    to_grid = np.where(worth_selling, np.minimum(available, grid.export_limit_mw), 0.0)
    zeros = np.zeros(price.size)
    return _plan(
        price,
        step_hours,
        grid.premium_per_mwh,
        0.0,
        to_grid=to_grid,
        to_battery=zeros,
        curtailed=available - to_grid,
        from_grid=zeros,
        discharge=zeros,
        energy=np.zeros(price.size + 1),
    )


def _plan(
    price: FloatArray,
    dt: float,
    premium: float,
    kappa: float,
    *,
    to_grid: FloatArray,
    to_battery: FloatArray,
    curtailed: FloatArray,
    from_grid: FloatArray,
    discharge: FloatArray,
    energy: FloatArray,
) -> ColocatedPlan:
    charge = to_battery + from_grid
    export = to_grid + discharge - from_grid
    revenue = float(price @ export * dt)
    premium_paid = float(premium * (to_grid + to_battery).sum() * dt)
    throughput = float((charge + discharge).sum() * dt)
    return ColocatedPlan(
        plant_to_grid_mw=to_grid,
        plant_to_battery_mw=to_battery,
        curtailed_mw=curtailed,
        grid_to_battery_mw=from_grid,
        charge_mw=charge,
        discharge_mw=discharge,
        export_mw=export,
        energy_mwh=energy,
        expected_revenue=revenue,
        expected_premium=premium_paid,
        objective=revenue + premium_paid - kappa * throughput,
    )


def _available(values: Sequence[float] | FloatArray, n: int) -> FloatArray:
    available = np.asarray(values, dtype=np.float64)
    if available.shape != (n,):
        raise DispatchError("available output and prices must have the same length")
    if not np.isfinite(available).all():
        raise DispatchError("available output must be finite")
    if (available < 0).any():
        raise DispatchError("available output must be non-negative")
    return available
