"""Summary metrics for backtest results."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from openenergy.backtest.engine import BacktestResult

DAYS_PER_YEAR = 365.0


@dataclass(frozen=True)
class Summary:
    """Headline results. Money is in ``currency``; energy in MWh.

    For a co-located site, ``revenue`` covers the whole site and the plant fields are set;
    per-MW and captured-spread figures apply to battery-only runs.
    """

    forecaster: str
    currency: str
    days: int
    skipped_days: int
    revenue: float
    revenue_per_mw_year: float | None
    charged_mwh: float
    discharged_mwh: float
    captured_spread: float | None
    equivalent_cycles: float
    final_soh: float
    forecast_mae: float
    forecast_rmse: float
    benchmark_revenue: float | None = None
    capture_ratio: float | None = None
    premium: float | None = None
    available_mwh: float | None = None
    curtailed_mwh: float | None = None
    emissions_t: float | None = None

    @property
    def total(self) -> float:
        """Market revenue plus any premium."""
        return self.revenue + (self.premium or 0.0)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def summarise(result: BacktestResult, benchmark: BacktestResult | None = None) -> Summary:
    """Summarise ``result``; ``capture_ratio`` compares with ``benchmark`` on common days."""
    daily = result.daily
    revenue = float(daily["revenue"].sum())
    discharged = float(daily["discharged_mwh"].sum())
    days = len(daily)
    error = (result.intervals["forecast"] - result.intervals["price"]).to_numpy(dtype=np.float64)
    site = result.site is not None

    benchmark_revenue: float | None = None
    capture_ratio: float | None = None
    if benchmark is not None:
        common = daily.index.intersection(benchmark.daily.index)
        benchmark_revenue = _total(benchmark.daily.loc[common])
        if benchmark_revenue > 0:
            capture_ratio = _total(daily.loc[common]) / benchmark_revenue

    return Summary(
        forecaster=result.forecaster,
        currency=result.currency,
        days=days,
        skipped_days=len(result.skipped),
        revenue=revenue,
        revenue_per_mw_year=None if site else revenue / result.spec.power_mw * DAYS_PER_YEAR / days,
        charged_mwh=float(daily["charged_mwh"].sum()),
        discharged_mwh=discharged,
        captured_spread=revenue / discharged if discharged > 0 and not site else None,
        equivalent_cycles=result.final_state.equivalent_cycles,
        final_soh=result.final_state.soh,
        forecast_mae=float(np.abs(error).mean()),
        forecast_rmse=float(np.sqrt((error**2).mean())),
        benchmark_revenue=benchmark_revenue,
        capture_ratio=capture_ratio,
        premium=float(daily["premium"].sum()) if site else None,
        available_mwh=float(daily["available_mwh"].sum()) if site else None,
        curtailed_mwh=float(daily["curtailed_mwh"].sum()) if site else None,
        emissions_t=float(daily["emissions_t"].sum()) if "emissions_t" in daily else None,
    )


def _total(daily: pd.DataFrame) -> float:
    premium = float(daily["premium"].sum()) if "premium" in daily else 0.0
    return float(daily["revenue"].sum()) + premium
