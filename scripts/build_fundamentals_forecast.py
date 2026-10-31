"""Build the fundamentals day-ahead forecast for every day from 2019 into data/forecasts/.

For each day, exactly what a backtest with ``forecast: fundamentals`` (noon the day before,
auction information, stretch chosen each month) would forecast, so the web app, the docs
and scenarios can use it without retraining. Model output, not source data.

Run: uv run --extra forecast python scripts/build_fundamentals_forecast.py [--start 2019-01-01]
"""

import argparse
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from openenergy.backtest.engine import known_until
from openenergy.data.ember import gb_prices
from openenergy.data.fundamentals import FUNDAMENTALS_FROM, FundamentalsSource
from openenergy.forecast.fundamentals import FundamentalsForecaster

DATA = Path(__file__).parents[1] / "data"
OUTPUT = DATA / "forecasts/gb_fundamentals_day_ahead.csv"
LEAD_HOURS = 12.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=date.fromisoformat, default=date(2019, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    args = parser.parse_args()
    prices = gb_prices([DATA / "prices/gb_day_ahead_ember.csv"], FUNDAMENTALS_FROM.date(), args.end)
    actual = prices[0].prices
    last = args.end or pd.DatetimeIndex(actual.index)[-1].date()
    forecaster = FundamentalsForecaster(FundamentalsSource(DATA / "fundamentals"), LEAD_HOURS)
    rows: list[pd.DataFrame] = []
    began = time.time()
    day = args.start
    while day <= last:
        start = pd.Timestamp(day, tz="UTC")
        index = pd.date_range(start, periods=24, freq="h")
        history = actual[actual.index < known_until(start, LEAD_HOURS, "auction")]
        values = forecaster.forecast(history, index)
        month = forecaster.months[start.replace(day=1)]
        rows.append(
            pd.DataFrame({"forecast_gbp_per_mwh": values.round(2), "stretch": month.stretch}, index)
        )
        if day.day == 1:
            print(f"{day:%Y-%m} stretch {month.stretch} ({time.time() - began:.0f} s)", flush=True)
        day += timedelta(days=1)
    out = pd.concat(rows)
    out.index = out.index.strftime("%Y-%m-%dT%H:%M:%SZ")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index_label="utc_timestamp")
    print(f"wrote {len(out)} hours to {OUTPUT}")


if __name__ == "__main__":
    main()
