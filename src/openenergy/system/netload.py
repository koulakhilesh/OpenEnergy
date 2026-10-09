"""Net load: demand left for dispatchable plant once wind and solar are subtracted."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from openenergy.data.opsd import OPSDCsvSource
from openenergy.data.quality import flag_glitches
from openenergy.errors import ConfigError

SYSTEM_COLUMNS = ["load_mw", "wind_mw", "solar_mw", "price"]
_HOUR = pd.Timedelta(hours=1)


@dataclass(frozen=True)
class NetLoadStats:
    """One calendar year of net load. Power in MW, energy in MWh, price slope per GW.

    Ramps are 99th percentiles of absolute changes, so a single bad reading cannot set them.
    """

    year: int
    hours: int
    renewable_share: float
    mean_net_mw: float
    peak_net_mw: float
    min_net_mw: float
    ramp_1h_p99_mw: float
    ramp_3h_p99_mw: float
    surplus_mwh: float
    surplus_hours: int
    surplus_share: float
    price_slope_per_gw: float | None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True, eq=False)
class SystemData:
    """Load, wind and solar (MW) and price on one UTC index.

    ``load_flagged`` counts load readings removed as telemetry glitches.
    """

    frame: pd.DataFrame
    load_flagged: int = 0


def load_system(
    source: OPSDCsvSource,
    zone: str,
    start: date | None = None,
    end: date | None = None,
    clean_load: bool = True,
) -> SystemData:
    """Load, wind and solar generation and day-ahead price, with load glitches removed."""
    load = source.load(zone, start, end)
    flagged = flag_glitches(load) if clean_load else pd.Series(False, index=load.index)
    columns = {
        "load_mw": load.mask(flagged),
        "wind_mw": source.generation(zone, "wind", start, end),
        "solar_mw": source.generation(zone, "solar", start, end),
        "price": source.prices(zone, start, end).prices,
    }
    frame = pd.concat(columns, axis=1)[SYSTEM_COLUMNS]
    return SystemData(frame, load_flagged=int(flagged.sum()))


def net_load(
    system: pd.DataFrame, scale_wind: float = 1.0, scale_solar: float = 1.0
) -> pd.Series[float]:
    """Load minus wind and solar, each scaled to model more (or less) installed capacity."""
    for name, value in (("scale_wind", scale_wind), ("scale_solar", scale_solar)):
        if not (math.isfinite(value) and value >= 0):
            raise ConfigError(f"{name} must be non-negative, got {value}")
    net = system["load_mw"] - scale_wind * system["wind_mw"] - scale_solar * system["solar_mw"]
    return net.rename("net_load_mw")


def surplus(net: pd.Series[float], must_run_mw: float = 0.0) -> pd.Series[float]:
    """Renewable output the system cannot use: how far net load falls below the must-run floor."""
    if not (math.isfinite(must_run_mw) and must_run_mw >= 0):
        raise ConfigError(f"must_run_mw must be non-negative, got {must_run_mw}")
    return (must_run_mw - net).clip(lower=0.0).rename("surplus_mw")


def duration_curve(net: pd.Series[float]) -> pd.Series[float]:
    """Values sorted high to low, indexed by the share of time at or above each value."""
    values = np.sort(net.dropna().to_numpy(dtype=np.float64))[::-1]
    share = np.arange(1, values.size + 1) / values.size
    return pd.Series(values, index=pd.Index(share, name="share_of_time"), name=net.name)


def netload_by_year(
    system: pd.DataFrame,
    scale_wind: float = 1.0,
    scale_solar: float = 1.0,
    must_run_mw: float = 0.0,
) -> list[NetLoadStats]:
    """Net-load statistics per UTC calendar year.

    The price slope is only meaningful for the system as it was, so it is omitted when
    renewables are scaled.
    """
    index = pd.DatetimeIndex(system.index)
    step = index[1] - index[0] if len(index) > 1 else _HOUR
    dt = float(step / _HOUR)
    net = net_load(system, scale_wind, scale_solar)
    renewables = scale_wind * system["wind_mw"] + scale_solar * system["solar_mw"]
    spill = surplus(net, must_run_mw)
    complete = system[["load_mw", "wind_mw", "solar_mw"]].notna().all(axis=1)
    actual_system = scale_wind == 1.0 and scale_solar == 1.0

    results = []
    for year in sorted(set(index.year)):
        in_year = (index.year == year) & complete.to_numpy()
        if not in_year.any():
            continue
        year_net = net[index.year == year].where(complete[index.year == year])
        load_energy = float(system.loc[in_year, "load_mw"].sum() * dt)
        renewable_energy = float(renewables[in_year].sum() * dt)
        surplus_energy = float(spill[in_year].sum() * dt)
        results.append(
            NetLoadStats(
                year=int(year),
                hours=int(in_year.sum()),
                renewable_share=renewable_energy / load_energy if load_energy else math.nan,
                mean_net_mw=float(year_net.mean()),
                peak_net_mw=float(year_net.max()),
                min_net_mw=float(year_net.min()),
                ramp_1h_p99_mw=float(year_net.diff(round(1 / dt)).abs().quantile(0.99)),
                ramp_3h_p99_mw=float(year_net.diff(round(3 / dt)).abs().quantile(0.99)),
                surplus_mwh=surplus_energy,
                surplus_hours=int((spill[in_year] > 0).sum()),
                surplus_share=surplus_energy / renewable_energy if renewable_energy else 0.0,
                price_slope_per_gw=_price_slope(net[in_year], system.loc[in_year, "price"])
                if actual_system
                else None,
            )
        )
    return results


def _price_slope(net: pd.Series[float], price: pd.Series[float]) -> float | None:
    pairs = pd.concat([net, price], axis=1).dropna()
    if len(pairs) < 2 or pairs.iloc[:, 0].nunique() < 2:
        return None
    slope = np.polyfit(pairs.iloc[:, 0].to_numpy(), pairs.iloc[:, 1].to_numpy(), 1)[0]
    return float(slope) * 1000.0
