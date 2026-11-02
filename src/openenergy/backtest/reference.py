"""The reference battery OpenEnergy values its studies with: 1 MW / 2 MWh, 95% each way, and
GBP 5/MWh of wear in the plan."""

from __future__ import annotations

import pandas as pd

from openenergy.assets.battery import BatterySpec
from openenergy.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from openenergy.data.series import PriceSeries
from openenergy.dispatch.arbitrage import DispatchConfig
from openenergy.forecast.baseline import PerfectForesight

REFERENCE_BATTERY = BatterySpec(power_mw=1.0, energy_mwh=2.0, eta_charge=0.95, eta_discharge=0.95)
REFERENCE_WEAR_GBP_PER_MWH = 5.0
REFERENCE_DISPATCH = DispatchConfig(degradation_cost=REFERENCE_WEAR_GBP_PER_MWH)
REFERENCE_CONFIG = BacktestConfig(dispatch=REFERENCE_DISPATCH)


def perfect_foresight_run(prices: pd.Series[float]) -> BacktestResult:
    """The reference battery planned with perfect foresight on ``prices`` (GBP/MWh)."""
    series = PriceSeries(prices, currency="GBP", zone="GB_GBN")
    return run_backtest(REFERENCE_BATTERY, series, PerfectForesight(series), REFERENCE_CONFIG)
