"""Summary metrics for backtest results."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

import numpy as np

from openenergy.backtest.engine import BacktestResult

DAYS_PER_YEAR = 365.0


@dataclass(frozen=True)
class Summary:
    """Headline results. Money is in ``currency``; energy in MWh."""

    forecaster: str
    currency: str
    days: int
    skipped_days: int
    revenue: float
    revenue_per_mw_year: float
    charged_mwh: float
    discharged_mwh: float
    captured_spread: float | None
    equivalent_cycles: float
    final_soh: float
    forecast_mae: float
    forecast_rmse: float
    benchmark_revenue: float | None = None
    capture_ratio: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def summarise(result: BacktestResult, benchmark: BacktestResult | None = None) -> Summary:
    """Summarise ``result``; ``capture_ratio`` compares with ``benchmark`` on common days."""
    daily = result.daily
    revenue = float(daily["revenue"].sum())
    discharged = float(daily["discharged_mwh"].sum())
    days = len(daily)
    error = (result.intervals["forecast"] - result.intervals["price"]).to_numpy(dtype=np.float64)

    benchmark_revenue: float | None = None
    capture_ratio: float | None = None
    if benchmark is not None:
        common = daily.index.intersection(benchmark.daily.index)
        benchmark_revenue = float(benchmark.daily.loc[common, "revenue"].sum())
        if benchmark_revenue > 0:
            capture_ratio = float(daily.loc[common, "revenue"].sum()) / benchmark_revenue

    return Summary(
        forecaster=result.forecaster,
        currency=result.currency,
        days=days,
        skipped_days=len(result.skipped),
        revenue=revenue,
        revenue_per_mw_year=revenue / result.spec.power_mw * DAYS_PER_YEAR / days,
        charged_mwh=float(daily["charged_mwh"].sum()),
        discharged_mwh=discharged,
        captured_spread=revenue / discharged if discharged > 0 else None,
        equivalent_cycles=result.final_state.equivalent_cycles,
        final_soh=result.final_state.soh,
        forecast_mae=float(np.abs(error).mean()),
        forecast_rmse=float(np.sqrt((error**2).mean())),
        benchmark_revenue=benchmark_revenue,
        capture_ratio=capture_ratio,
    )
