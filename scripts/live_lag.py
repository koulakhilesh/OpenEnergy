"""How much a live forecast loses when published prices lag: the fundamentals forecast for
each day of a year, made with prices up to the auction (as in the backtest) and with the
last two, three or four days of prices missing (Ember publishes about two days late).

Writes data/forecasts/live_lag_YEAR.csv: one row per day, the mean absolute error of each
forecast, and of last week's prices, against the day-ahead price. Model output.

Run: uv run --extra forecast python scripts/live_lag.py [--year 2025]
"""

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from openenergy.backtest.engine import known_until
from openenergy.data.ember import gb_prices
from openenergy.data.fundamentals import FUNDAMENTALS_FROM, FundamentalsSource
from openenergy.forecast.baseline import NaiveLastWeek
from openenergy.forecast.fundamentals import FundamentalsForecaster

DATA = Path(__file__).parents[1] / "data"
LEAD_HOURS = 12.0
LAGS = (2, 3, 4)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", type=int, default=2025)
    args = parser.parse_args()
    end = date(args.year, 12, 31)
    prices = gb_prices([DATA / "prices/gb_day_ahead_ember.csv"], FUNDAMENTALS_FROM.date(), end)
    actual = prices[0].prices
    forecaster = FundamentalsForecaster(FundamentalsSource(DATA / "fundamentals"), LEAD_HOURS)
    naive = NaiveLastWeek()
    rows = []
    for day in pd.date_range(f"{args.year}-01-01", end, tz="UTC"):
        index = pd.date_range(day, periods=24, freq="h")
        real = actual.reindex(index).to_numpy(dtype=np.float64)
        if np.isnan(real).any():
            continue
        history = actual[actual.index < known_until(day, LEAD_HOURS, "auction")].dropna()
        row = {
            "date": day.date().isoformat(),
            "mae_auction": np.abs(forecaster.forecast(history, index) - real).mean(),
            "mae_last_week": np.abs(naive.forecast(history, index) - real).mean(),
        }
        for lag in LAGS:
            known = history[history.index < day - pd.Timedelta(days=lag)]
            cutoff = known.index.max() + pd.Timedelta(hours=1)
            row[f"mae_lag_{lag}d"] = np.abs(forecaster.forecast(known, index, cutoff) - real).mean()
        rows.append(row)
    table = pd.DataFrame(rows).round(3)
    out = DATA / f"forecasts/live_lag_{args.year}.csv"
    table.to_csv(out, index=False)
    print(table.drop(columns="date").mean().round(2).to_string())
    print(f"wrote {len(table)} days to {out}")


if __name__ == "__main__":
    main()
