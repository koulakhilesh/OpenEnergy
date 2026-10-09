"""How much is a better price forecast worth to a battery?

Backtests GB 2019 with perfect prices plus Gaussian error of increasing size and reports
the share of perfect-foresight revenue captured.

Run: uv run python examples/forecast_error_sweep.py
"""

from datetime import date
from pathlib import Path

from openenergy.assets import BatterySpec
from openenergy.backtest import BacktestConfig, run_backtest
from openenergy.data import OPSDCsvSource, fill_gaps
from openenergy.dispatch import DispatchConfig
from openenergy.forecast import NoisyForesight, PerfectForesight
from openenergy.metrics import summarise

DATA = Path(__file__).parents[1] / "data/time_series/time_series_60min_singleindex_filtered.csv"
ERROR_STDS = (0.0, 2.0, 5.0, 10.0, 20.0)


def main() -> None:
    raw = OPSDCsvSource(DATA).prices("GB_GBN", date(2019, 1, 1), date(2019, 12, 31))
    prices, _ = fill_gaps(raw, max_gap_hours=2)
    battery = BatterySpec(power_mw=1, energy_mwh=2)
    config = BacktestConfig(dispatch=DispatchConfig(degradation_cost=5))
    benchmark = run_backtest(battery, prices, PerfectForesight(prices), config)

    print(f"{'error std (GBP/MWh)':>20}{'revenue (GBP)':>15}{'capture':>10}{'cycles':>8}")
    for error_std in ERROR_STDS:
        forecaster = NoisyForesight(prices, error_std=error_std, seed=1)
        summary = summarise(run_backtest(battery, prices, forecaster, config), benchmark)
        capture = summary.capture_ratio or 0.0
        print(
            f"{error_std:>20.0f}{summary.revenue:>15,.0f}{capture:>10.1%}"
            f"{summary.equivalent_cycles:>8.0f}"
        )


if __name__ == "__main__":
    main()
