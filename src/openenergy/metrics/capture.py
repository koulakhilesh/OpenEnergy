"""Captured price: what the market pays a generator for the hours it actually produces."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from openenergy.data.series import PriceSeries, ProfileSeries
from openenergy.errors import DataError


@dataclass(frozen=True)
class CaptureMetrics:
    """Market value of a generation profile. Prices in ``currency``/MWh, energy in MWh."""

    label: str
    currency: str
    intervals: int
    energy_mwh: float
    capacity_factor: float
    baseload_price: float
    revenue: float
    captured_price: float | None
    capture_rate: float | None
    negative_price_share: float | None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def capture_metrics(
    prices: PriceSeries,
    generation_mw: pd.Series[float],
    capacity_mw: float,
    label: str = "all",
) -> CaptureMetrics:
    """Captured price, capture rate and related metrics over intervals with both values.

    Capture rate is captured price divided by the time-weighted (baseload) price.
    """
    frame = pd.concat({"price": prices.prices, "mw": generation_mw}, axis=1, join="inner").dropna()
    if frame.empty:
        raise DataError(f"prices and generation do not overlap for {label}")
    dt = prices.step_hours
    price = frame["price"].to_numpy(dtype=np.float64)
    energy = frame["mw"].to_numpy(dtype=np.float64) * dt
    total = float(energy.sum())
    revenue = float(price @ energy)
    baseload = float(price.mean())
    captured = revenue / total if total > 0 else None
    return CaptureMetrics(
        label=label,
        currency=prices.currency,
        intervals=len(frame),
        energy_mwh=total,
        capacity_factor=total / (capacity_mw * dt * len(frame)),
        baseload_price=baseload,
        revenue=revenue,
        captured_price=captured,
        capture_rate=captured / baseload if captured is not None and baseload > 0 else None,
        negative_price_share=float(energy[price < 0].sum()) / total if total > 0 else None,
    )


def capture_by_year(prices: PriceSeries, profile: ProfileSeries) -> list[CaptureMetrics]:
    """Capture metrics per calendar year (UTC) for 1 MW of ``profile``."""
    values = profile.values
    years = sorted(set(pd.DatetimeIndex(values.dropna().index).year))
    results = []
    for year in years:
        in_year = values[pd.DatetimeIndex(values.index).year == year]
        try:
            results.append(capture_metrics(prices, in_year, capacity_mw=1.0, label=str(year)))
        except DataError:
            continue
    return results
