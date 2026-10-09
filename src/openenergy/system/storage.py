"""How much system surplus a storage fleet can absorb."""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from openenergy.errors import ConfigError

_HOUR = pd.Timedelta(hours=1)


@dataclass(frozen=True, eq=False)
class FleetResult:
    """Surplus absorbed by a fleet of ``power_mw`` and ``hours`` duration; energy in MWh.

    ``residual`` is net load after storage, relative to the must-run floor's surplus rule.
    """

    power_mw: float
    hours: float
    surplus_mwh: float
    absorbed_mwh: float
    released_mwh: float
    residual: pd.Series[float] = field(repr=False)

    @property
    def energy_mwh(self) -> float:
        return self.power_mw * self.hours

    @property
    def absorbed_share(self) -> float:
        return self.absorbed_mwh / self.surplus_mwh if self.surplus_mwh > 0 else 0.0

    @property
    def equivalent_cycles(self) -> float:
        return (self.absorbed_mwh + self.released_mwh) / (2 * self.energy_mwh)


def absorb_surplus(
    net: pd.Series[float],
    power_mw: float,
    hours: float,
    eta_charge: float = 0.95,
    eta_discharge: float = 0.95,
    must_run_mw: float = 0.0,
) -> FleetResult:
    """Charge from surplus (net load below ``must_run_mw``), release when net load is above it.

    Greedy in time order: release only as much as keeps net load at or above the floor, so
    storage never creates new surplus. Missing hours are idle.
    """
    for name, value in (("power_mw", power_mw), ("hours", hours)):
        if not (math.isfinite(value) and value > 0):
            raise ConfigError(f"{name} must be positive, got {value}")
    for name, value in (("eta_charge", eta_charge), ("eta_discharge", eta_discharge)):
        if not 0 < value <= 1:
            raise ConfigError(f"{name} must be in (0, 1], got {value}")
    index = pd.DatetimeIndex(net.index)
    dt = float((index[1] - index[0]) / _HOUR) if len(index) > 1 else 1.0
    capacity = power_mw * hours
    values: list[float] = net.astype(float).tolist()
    residual = np.array(values, dtype=np.float64)
    stored = absorbed = released = surplus_total = 0.0

    for t, level in enumerate(values):
        if math.isnan(level):
            continue
        gap = level - must_run_mw
        if gap < 0:
            surplus_total += -gap * dt
            charge = min(power_mw, -gap, (capacity - stored) / (eta_charge * dt))
            stored += eta_charge * charge * dt
            absorbed += charge * dt
            residual[t] = level + charge
        elif gap > 0 and stored > 0:
            discharge = min(power_mw, gap, stored * eta_discharge / dt)
            stored -= discharge * dt / eta_discharge
            released += discharge * dt
            residual[t] = level - discharge

    return FleetResult(
        power_mw=power_mw,
        hours=hours,
        surplus_mwh=surplus_total,
        absorbed_mwh=absorbed,
        released_mwh=released,
        residual=pd.Series(residual, index=net.index, name="net_after_storage_mw"),
    )


def sizing_grid(
    net: pd.Series[float],
    powers_mw: Iterable[float],
    hours: Iterable[float],
    eta_charge: float = 0.95,
    eta_discharge: float = 0.95,
    must_run_mw: float = 0.0,
) -> pd.DataFrame:
    """``absorb_surplus`` for every power and duration combination."""
    rows = []
    for power, duration in itertools.product(powers_mw, hours):
        fleet = absorb_surplus(net, power, duration, eta_charge, eta_discharge, must_run_mw)
        rows.append(
            {
                "power_mw": power,
                "hours": duration,
                "energy_mwh": fleet.energy_mwh,
                "absorbed_share": fleet.absorbed_share,
                "absorbed_mwh": fleet.absorbed_mwh,
                "released_mwh": fleet.released_mwh,
                "equivalent_cycles": fleet.equivalent_cycles,
            }
        )
    return pd.DataFrame(rows)
