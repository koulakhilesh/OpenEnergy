"""How big should the shared connection be for solar plus storage?

Backtests GB 2019 for 10 MW of solar and a 5 MW / 10 MWh battery behind one connection of
increasing size, and compares each with the same assets on separate connections (15 MW).

Run: uv run python examples/colocation_grid_sweep.py
"""

from datetime import date
from pathlib import Path

import pandas as pd

from openenergy.assets import BatterySpec, RenewableSpec
from openenergy.backtest import BacktestConfig, Site, run_backtest, run_plant_backtest
from openenergy.data import OPSDCsvSource, fill_gaps
from openenergy.dispatch import DispatchConfig, GridConnection
from openenergy.forecast import NaiveLastWeek

DATA = Path(__file__).parents[1] / "data/time_series/time_series_60min_singleindex_filtered.csv"
START, END = date(2019, 1, 1), date(2019, 12, 29)
LIMITS_MW = (5.0, 7.0, 10.0, 12.5, 15.0)


def daily_total(daily: pd.DataFrame) -> pd.Series:
    return daily["revenue"] + daily.get("premium", 0.0)


def main() -> None:
    source = OPSDCsvSource(DATA)
    prices, _ = fill_gaps(source.prices("GB_GBN", date(2018, 12, 18), END), 2)
    profile, _ = fill_gaps(source.profile("GB_GBN", "solar", date(2018, 12, 18), END), 2)
    plant = RenewableSpec("solar", capacity_mw=10)
    output = plant.generation_mw(profile)
    battery = BatterySpec(power_mw=5, energy_mwh=10)
    config = BacktestConfig(dispatch=DispatchConfig(degradation_cost=5))
    forecaster = NaiveLastWeek()
    days = list(pd.date_range(START, END).date)

    own_connection = GridConnection(10, import_limit_mw=0)
    alone = run_plant_backtest(Site(output, own_connection), prices, forecaster, config, days)
    storage = run_backtest(battery, prices, forecaster, config, days)
    separate = daily_total(alone.daily).add(daily_total(storage.daily), fill_value=None)

    print(f"{'shared limit (MW)':>18}{'site (GBP)':>14}{'separate (GBP)':>16}{'difference':>12}")
    for limit in LIMITS_MW:
        site = Site(output, GridConnection(limit))
        result = run_backtest(battery, prices, forecaster, config, days, site=site)
        shared = daily_total(result.daily)
        common = shared.index.intersection(separate.dropna().index)
        together, apart = float(shared[common].sum()), float(separate[common].sum())
        print(f"{limit:>18.1f}{together:>14,.0f}{apart:>16,.0f}{together - apart:>12,.0f}")


if __name__ == "__main__":
    main()
