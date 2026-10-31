"""How much of a battery's perfect-foresight revenue does each forecast capture, year by year?

Backtests a 1 MW / 2 MWh battery on GB day-ahead prices (Ember) for each calendar year
from 2019, planning at noon the day before on last week's prices or on the bundled
fundamentals forecast (data/forecasts, built by scripts/build_fundamentals_forecast.py),
and reports revenue, the share of perfect-foresight revenue captured and the mean
absolute forecast error.

Run: uv run python examples/fundamentals_forecast.py
"""

from datetime import date
from pathlib import Path

from openenergy.assets import BatterySpec
from openenergy.backtest import BacktestConfig, run_backtest
from openenergy.data.ember import gb_prices
from openenergy.dispatch import DispatchConfig
from openenergy.forecast import NaiveLastWeek, PerfectForesight, PrecomputedForecast
from openenergy.metrics import summarise

DATA = Path(__file__).parents[1] / "data"
FORECAST = DATA / "forecasts/gb_fundamentals_day_ahead.csv"


def main() -> None:
    battery = BatterySpec(power_mw=1, energy_mwh=2, eta_charge=0.95, eta_discharge=0.95)
    config = BacktestConfig(dispatch=DispatchConfig(degradation_cost=5))
    fundamentals = PrecomputedForecast(FORECAST, name="fundamentals")
    print(f"{'year':>6}{'forecast':>17}{'revenue (GBP)':>15}{'capture':>9}{'MAE':>7}")
    for year in range(2019, 2027):
        prices = gb_prices([DATA / "prices/gb_day_ahead_ember.csv"], date(year - 1, 12, 1),
                           date(year, 12, 31))[0]  # fmt: skip
        days = sorted({d for d in prices.prices.index.date if d.year == year})
        benchmark = run_backtest(battery, prices, PerfectForesight(prices), config, days)
        print(f"{year:>6}{'perfect':>17}{summarise(benchmark).revenue:>15,.0f}")
        for forecaster in (NaiveLastWeek(), fundamentals):
            run = run_backtest(battery, prices, forecaster, config, days)
            summary = summarise(run, benchmark=benchmark)
            error = (run.intervals["forecast"] - run.intervals["price"]).abs().mean()
            capture = summary.capture_ratio or 0.0
            print(
                f"{year:>6}{forecaster.name:>17}{summary.revenue:>15,.0f}"
                f"{capture:>9.1%}{error:>7.1f}"
            )


if __name__ == "__main__":
    main()
