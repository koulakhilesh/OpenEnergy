"""Battery specification, state and physics."""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from openenergy.errors import ConfigError, DispatchError

HOURS_PER_YEAR = 8760.0
# Absolute slack (MW or MWh) for solver round-off before a dispatch is rejected.
TOLERANCE = 1e-6

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class BatteryState:
    """Physical state carried between intervals."""

    energy_mwh: float
    soh: float = 1.0
    throughput_mwh: float = 0.0
    equivalent_cycles: float = 0.0
    age_years: float = 0.0


@dataclass(frozen=True)
class BatterySpec:
    """Battery ratings. SOC limits are fractions of usable (degraded) energy."""

    power_mw: float
    energy_mwh: float
    eta_charge: float = 0.95
    eta_discharge: float = 0.95
    soc_min: float = 0.0
    soc_max: float = 1.0
    initial_soc: float = 0.5
    cycle_fade: float = 0.0
    calendar_fade: float = 0.0

    def __post_init__(self) -> None:
        for field in dataclasses.fields(self):
            if not math.isfinite(getattr(self, field.name)):
                raise ConfigError(f"{field.name} must be finite")
        if self.power_mw <= 0:
            raise ConfigError(f"power_mw must be positive, got {self.power_mw}")
        if self.energy_mwh <= 0:
            raise ConfigError(f"energy_mwh must be positive, got {self.energy_mwh}")
        for name in ("eta_charge", "eta_discharge"):
            value = getattr(self, name)
            if not 0 < value <= 1:
                raise ConfigError(f"{name} must be in (0, 1], got {value}")
        for name in ("soc_min", "soc_max"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ConfigError(f"{name} must be in [0, 1], got {value}")
        if self.soc_min >= self.soc_max:
            raise ConfigError(f"soc_min ({self.soc_min}) must be below soc_max ({self.soc_max})")
        if not self.soc_min <= self.initial_soc <= self.soc_max:
            raise ConfigError(
                f"initial_soc ({self.initial_soc}) must lie within "
                f"[soc_min, soc_max] = [{self.soc_min}, {self.soc_max}]"
            )
        for name in ("cycle_fade", "calendar_fade"):
            value = getattr(self, name)
            if not 0 <= value < 1:
                raise ConfigError(f"{name} must be in [0, 1), got {value}")

    def initial_state(self) -> BatteryState:
        return BatteryState(energy_mwh=self.initial_soc * self.energy_mwh)

    def usable_energy_mwh(self, state: BatteryState) -> float:
        return self.energy_mwh * state.soh

    def energy_bounds(self, state: BatteryState) -> tuple[float, float]:
        usable = self.usable_energy_mwh(state)
        return self.soc_min * usable, self.soc_max * usable


@dataclass(frozen=True)
class DispatchOutcome:
    """State after a dispatch and the stored energy at each interval boundary."""

    state: BatteryState
    energy_mwh: FloatArray


def apply_dispatch(
    spec: BatterySpec,
    state: BatteryState,
    charge_mw: Sequence[float] | FloatArray,
    discharge_mw: Sequence[float] | FloatArray,
    step_hours: float,
) -> DispatchOutcome:
    """Apply a charge/discharge schedule (MW per interval) and return the new state."""
    if step_hours <= 0:
        raise DispatchError(f"step_hours must be positive, got {step_hours}")
    charge = _as_power(charge_mw)
    discharge = _as_power(discharge_mw)
    if charge.ndim != 1 or discharge.ndim != 1:
        raise DispatchError("charge and discharge must be one-dimensional")
    if charge.shape != discharge.shape:
        raise DispatchError("charge and discharge must have the same length")
    if not (np.isfinite(charge).all() and np.isfinite(discharge).all()):
        raise DispatchError("charge and discharge must be finite")
    _check_power(spec, charge, "charge")
    _check_power(spec, discharge, "discharge")
    both = np.flatnonzero((charge > TOLERANCE) & (discharge > TOLERANCE))
    if both.size:
        raise DispatchError(f"simultaneous charge and discharge in interval {both[0]}")

    charge = np.clip(charge, 0.0, spec.power_mw)
    discharge = np.clip(discharge, 0.0, spec.power_mw)
    lower, upper = spec.energy_bounds(state)
    energy = np.empty(charge.size + 1)
    energy[0] = state.energy_mwh
    for t in range(charge.size):
        delta = spec.eta_charge * charge[t] - discharge[t] / spec.eta_discharge
        stored = energy[t] + delta * step_hours
        if stored > upper + TOLERANCE:
            raise DispatchError(
                f"interval {t}: stored energy {stored:.6f} MWh above maximum {upper:.6f} MWh"
            )
        if stored < lower - TOLERANCE:
            raise DispatchError(
                f"interval {t}: stored energy {stored:.6f} MWh below minimum {lower:.6f} MWh"
            )
        energy[t + 1] = min(max(stored, lower), upper)

    throughput = float((charge + discharge).sum() * step_hours)
    new_state = dataclasses.replace(
        state,
        energy_mwh=float(energy[-1]),
        throughput_mwh=state.throughput_mwh + throughput,
        equivalent_cycles=state.equivalent_cycles + throughput / (2 * spec.energy_mwh),
    )
    return DispatchOutcome(state=new_state, energy_mwh=energy)


def age(spec: BatterySpec, state: BatteryState, hours: float) -> BatteryState:
    """Advance calendar age and recompute state of health from lifetime totals."""
    if hours < 0:
        raise DispatchError(f"hours must be non-negative, got {hours}")
    age_years = state.age_years + hours / HOURS_PER_YEAR
    soh = 1.0 - spec.cycle_fade * state.equivalent_cycles - spec.calendar_fade * age_years
    aged = dataclasses.replace(state, soh=max(soh, 0.0), age_years=age_years)
    lower, upper = spec.energy_bounds(aged)
    return dataclasses.replace(aged, energy_mwh=min(max(state.energy_mwh, lower), upper))


def _as_power(values: Sequence[float] | FloatArray) -> FloatArray:
    return np.asarray(values, dtype=np.float64)


def _check_power(spec: BatterySpec, values: FloatArray, name: str) -> None:
    negative = np.flatnonzero(values < -TOLERANCE)
    if negative.size:
        raise DispatchError(f"{name} is negative in interval {negative[0]}")
    over = np.flatnonzero(values > spec.power_mw + TOLERANCE)
    if over.size:
        raise DispatchError(
            f"{name} {values[over[0]]:.6f} MW exceeds power rating "
            f"{spec.power_mw} MW in interval {over[0]}"
        )
