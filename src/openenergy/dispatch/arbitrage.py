"""Single-battery energy arbitrage as a mixed-integer linear programme (HiGHS)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from openenergy.assets.battery import TOLERANCE, BatterySpec, BatteryState
from openenergy.data.response import Service
from openenergy.dispatch._milp import INF, FloatArray, Row, clean, solve_milp, validate_horizon
from openenergy.errors import ConfigError, InfeasibleDispatchError

# Naive last-week forecasts stay before the decision time for up to six days ahead.
MAX_LOOKAHEAD_DAYS = 6


@dataclass(frozen=True)
class DispatchConfig:
    """Optimisation settings.

    ``end_soc`` is a fraction of usable energy; ``None`` means return to the starting energy.
    ``max_cycles`` caps equivalent full cycles over the horizon (the backtest scales it by
    the days planned, so it stays a per-day cap). ``lookahead_days`` makes the backtest plan
    each day together with that many following days of forecasts, settling only the first;
    the end-energy target then applies at the end of the last day.
    """

    end_soc: float | None = None
    degradation_cost: float = 0.0
    max_cycles: float | None = None
    mip_rel_gap: float = 1e-6
    lookahead_days: int = 0

    def __post_init__(self) -> None:
        if self.end_soc is not None and not 0 <= self.end_soc <= 1:
            raise ConfigError(f"end_soc must be in [0, 1], got {self.end_soc}")
        if not (math.isfinite(self.degradation_cost) and self.degradation_cost >= 0):
            raise ConfigError(f"degradation_cost must be non-negative, got {self.degradation_cost}")
        if self.max_cycles is not None and not self.max_cycles > 0:
            raise ConfigError(f"max_cycles must be positive, got {self.max_cycles}")
        if not self.mip_rel_gap >= 0:
            raise ConfigError(f"mip_rel_gap must be non-negative, got {self.mip_rel_gap}")
        if not 0 <= self.lookahead_days <= MAX_LOOKAHEAD_DAYS:
            raise ConfigError(
                f"lookahead_days must be 0 to {MAX_LOOKAHEAD_DAYS}, got {self.lookahead_days}"
            )


@dataclass(frozen=True)
class DispatchPlan:
    """Optimal schedule in MW per interval and stored energy at each boundary (T+1).

    With frequency response, ``reserve_mw`` is MW held per block and service, and
    ``response_charge_mw``/``response_discharge_mw`` the expected average power it moves.
    ``expected_revenue`` covers energy; ``expected_response`` the availability payments.
    """

    charge_mw: FloatArray
    discharge_mw: FloatArray
    energy_mwh: FloatArray
    expected_revenue: float
    objective: float
    reserve_mw: FloatArray | None = None
    response_charge_mw: FloatArray | None = None
    response_discharge_mw: FloatArray | None = None
    expected_response: float = 0.0


@dataclass(frozen=True, eq=False)
class Reserve:
    """Frequency-response options over a horizon.

    ``block`` maps each interval to a row of ``price`` (-1 where nothing can be reserved).
    ``price`` (GBP/MW/h) and ``utilisation`` (MWh delivered per MW per hour) have one row
    per block and one column per service. ``fixed`` holds MW already committed (NaN where
    free). ``beyond_hours`` is how long each block runs past the horizon end; the plan keeps
    enough energy to stay idle through it. With ``energy_paid``, delivered energy is bought
    or sold at the interval's price; otherwise it is free, as under NESO's ABSVD adjustment.
    """

    services: tuple[Service, ...]
    block: npt.NDArray[np.int64]
    price: FloatArray
    utilisation: FloatArray
    fixed: FloatArray | None = None
    energy_paid: bool = False
    beyond_hours: FloatArray | None = None

    def __post_init__(self) -> None:
        shape = (int(self.block.max(initial=-1)) + 1, len(self.services))
        for name in ("price", "utilisation", "fixed"):
            value = getattr(self, name)
            if value is not None and value.shape != shape:
                raise ConfigError(f"reserve {name} must have shape {shape}, got {value.shape}")
        if self.beyond_hours is not None and self.beyond_hours.shape != shape[:1]:
            raise ConfigError(f"reserve beyond_hours must have {shape[0]} blocks")
        if not (np.isfinite(self.price).all() and np.isfinite(self.utilisation).all()):
            raise ConfigError("reserve prices and utilisation must be finite")
        if ((self.utilisation < 0) | (self.utilisation > 1)).any():
            raise ConfigError("reserve utilisation must be in [0, 1]")

    def signs(self) -> FloatArray:
        """+1 for services that export (low), -1 for those that import (high)."""
        return np.array([1.0 if s.direction == "low" else -1.0 for s in self.services])

    def flows(self, reserve_mw: FloatArray) -> tuple[FloatArray, FloatArray]:
        """Average charge and discharge MW from responding, per interval."""
        moved = np.zeros((self.block.size, len(self.services)))
        inside = self.block >= 0
        moved[inside] = (reserve_mw * self.utilisation)[self.block[inside]]
        low = self.signs() > 0
        return moved[:, ~low].sum(axis=1), moved[:, low].sum(axis=1)

    def payment(self, reserve_mw: FloatArray, price: FloatArray, step_hours: float) -> float:
        """Availability payments for the intervals in the horizon at ``price`` per block."""
        inside = self.block >= 0
        return float((reserve_mw * price)[self.block[inside]].sum() * step_hours)


def optimise_dispatch(
    spec: BatterySpec,
    state: BatteryState,
    prices: Sequence[float] | FloatArray,
    step_hours: float,
    config: DispatchConfig | None = None,
    reserve: Reserve | None = None,
) -> DispatchPlan:
    """Maximise arbitrage (and response) revenue less degradation cost over the horizon."""
    config = config or DispatchConfig()
    price = validate_horizon(prices, step_hours)

    n = price.size
    dt = step_hours
    power = spec.power_mw
    lower, upper, target = energy_window(spec, state, config)
    usable = spec.usable_energy_mwh(state)
    if reserve is not None and reserve.block.shape != (n,):
        raise ConfigError(f"reserve block map must have {n} intervals")
    blocks, k = (0, 0) if reserve is None else reserve.price.shape

    # Columns: charge c[0:n], discharge d[n:2n], energy e[2n:3n+1], reserve r (blocks x k),
    # then the on-charge flag u (integers last).
    c, d, e, r = 0, n, 2 * n, 3 * n + 1
    u = r + blocks * k
    num_col = u + n
    cost = np.zeros(num_col)
    cost[c : c + n] = -(price + config.degradation_cost) * dt
    cost[d : d + n] = (price - config.degradation_cost) * dt

    col_lower = np.zeros(num_col)
    col_upper = np.full(num_col, power, dtype=np.float64)
    col_lower[e : e + n + 1] = lower
    col_upper[e : e + n + 1] = upper
    col_lower[e] = col_upper[e] = state.energy_mwh
    col_lower[e + n] = target
    col_upper[u : u + n] = 1.0

    rows: list[Row] = []
    throughput: dict[int, float] = {i: dt for i in range(c, c + 2 * n)}
    if reserve is not None:
        _reserve_columns(reserve, price, dt, config, r, cost, col_lower, col_upper, throughput)
        _reserve_limits(spec, reserve, rows, r, e + n, lower, upper)
    for t in range(n):
        cols = [e + t + 1, e + t, c + t, d + t]
        values = [1.0, -1.0, -spec.eta_charge * dt, dt / spec.eta_discharge]
        if reserve is not None and reserve.block[t] >= 0:
            extra_cols, extra_values = _reserve_rows(
                spec, reserve, t, rows, (c, d, e, r), dt, lower, upper
            )
            cols += extra_cols
            values += extra_values
        rows.append((cols, values, 0.0, 0.0))
        rows.append(([c + t, u + t], [1.0, -power], -INF, 0.0))
        rows.append(([d + t, u + t], [1.0, power], -INF, power))
    if config.max_cycles is not None:
        rows.append(
            (list(throughput), list(throughput.values()), -INF, 2 * config.max_cycles * usable)
        )

    solution = solve_milp(cost, col_lower, col_upper, rows, u, config.mip_rel_gap)
    charge = clean(solution[c : c + n], power)
    discharge = clean(solution[d : d + n], power)
    energy = np.asarray(solution[e : e + n + 1], dtype=np.float64)
    revenue = float(price @ (discharge - charge) * dt)
    moved = float((charge + discharge).sum() * dt)
    if reserve is None:
        return DispatchPlan(
            charge_mw=charge,
            discharge_mw=discharge,
            energy_mwh=energy,
            expected_revenue=revenue,
            objective=revenue - config.degradation_cost * moved,
        )
    held = clean(solution[r:u], power).reshape(blocks, k)
    if reserve.fixed is not None:
        held = np.where(np.isnan(reserve.fixed), held, reserve.fixed)
    response_in, response_out = reserve.flows(held)
    if reserve.energy_paid:
        revenue += float(price @ (response_out - response_in) * dt)
    payment = reserve.payment(held, reserve.price, dt)
    moved += float((response_in + response_out).sum() * dt)
    return DispatchPlan(
        charge_mw=charge,
        discharge_mw=discharge,
        energy_mwh=energy,
        expected_revenue=revenue,
        objective=revenue + payment - config.degradation_cost * moved,
        reserve_mw=held,
        response_charge_mw=response_in,
        response_discharge_mw=response_out,
        expected_response=payment,
    )


def _reserve_columns(
    reserve: Reserve,
    price: FloatArray,
    dt: float,
    config: DispatchConfig,
    r: int,
    cost: FloatArray,
    col_lower: FloatArray,
    col_upper: FloatArray,
    throughput: dict[int, float],
) -> None:
    """Objective, bounds and cycle-cap terms of the reserve columns."""
    blocks, k = reserve.price.shape
    hours = np.zeros(blocks)
    energy_value = np.zeros(blocks)
    for t, b in enumerate(reserve.block):
        if b >= 0:
            hours[b] += dt
            energy_value[b] += price[t] * dt
    for b in range(blocks):
        for j in range(k):
            col = r + b * k + j
            used = reserve.utilisation[b, j]
            cost[col] = (reserve.price[b, j] - config.degradation_cost * used) * hours[b]
            if reserve.energy_paid:
                cost[col] += reserve.signs()[j] * used * energy_value[b]
            throughput[col] = used * hours[b]
            if reserve.fixed is not None and np.isfinite(reserve.fixed[b, j]):
                col_lower[col] = col_upper[col] = reserve.fixed[b, j]


def _reserve_limits(
    spec: BatterySpec,
    reserve: Reserve,
    rows: list[Row],
    r: int,
    end: int,
    lower: float,
    upper: float,
) -> None:
    """Contracted MW per direction within the rating; energy for blocks past the horizon."""
    blocks, k = reserve.price.shape
    beyond = np.zeros(blocks) if reserve.beyond_hours is None else reserve.beyond_hours
    for b in range(blocks):
        for direction in ("low", "high"):
            picked = [j for j, s in enumerate(reserve.services) if s.direction == direction]
            if not picked:
                continue
            cols = [r + b * k + j for j in picked]
            rows.append((cols, [1.0] * len(cols), -INF, spec.power_mw))
            if beyond[b] <= 0:
                continue
            # Idle until the block ends: hold the service duration plus the energy it moves.
            need = [
                reserve.services[j].duration_hours + beyond[b] * reserve.utilisation[b, j]
                for j in picked
            ]
            if direction == "low":
                values = [-x / spec.eta_discharge for x in need]
                rows.append(([end, *cols], [1.0, *values], lower, INF))
            else:
                values = [x * spec.eta_charge for x in need]
                rows.append(([end, *cols], [1.0, *values], -INF, upper))


def _reserve_rows(
    spec: BatterySpec,
    reserve: Reserve,
    t: int,
    rows: list[Row],
    offsets: tuple[int, int, int, int],
    dt: float,
    lower: float,
    upper: float,
) -> tuple[list[int], list[float]]:
    """Add power headroom and energy-held rows; return response terms of the balance row."""
    c, d, e, r = offsets
    b = int(reserve.block[t])
    k = len(reserve.services)
    cols = [r + b * k + j for j in range(k)]
    low = [s.direction == "low" for s in reserve.services]
    drift = []
    for j in range(k):
        used = reserve.utilisation[b, j]
        gain = -used / spec.eta_discharge if low[j] else used * spec.eta_charge
        drift.append(-gain * dt)
    low_cols = [col for j, col in enumerate(cols) if low[j]]
    high_cols = [col for j, col in enumerate(cols) if not low[j]]
    power = spec.power_mw
    rows.append(([d + t, c + t, *low_cols], [1.0, -1.0, *[1.0] * len(low_cols)], -INF, power))
    rows.append(([c + t, d + t, *high_cols], [1.0, -1.0, *[1.0] * len(high_cols)], -INF, power))
    held_out = [reserve.services[j].duration_hours / spec.eta_discharge for j in range(k) if low[j]]
    held_in = [reserve.services[j].duration_hours * spec.eta_charge for j in range(k) if not low[j]]
    for boundary in (e + t, e + t + 1):
        if low_cols:
            rows.append(([boundary, *low_cols], [1.0, *(-x for x in held_out)], lower, INF))
        if high_cols:
            rows.append(([boundary, *high_cols], [1.0, *held_in], -INF, upper))
    return cols, drift


def energy_window(
    spec: BatterySpec, state: BatteryState, config: DispatchConfig
) -> tuple[float, float, float]:
    """Stored-energy bounds and the end-of-horizon target, in MWh."""
    lower, upper = spec.energy_bounds(state)
    usable = spec.usable_energy_mwh(state)
    target = state.energy_mwh if config.end_soc is None else config.end_soc * usable
    if target > upper + TOLERANCE:
        raise InfeasibleDispatchError(
            f"end energy target {target:.6f} MWh exceeds maximum {upper:.6f} MWh"
        )
    return lower, upper, max(lower, min(target, upper))
