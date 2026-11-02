"""Does supply tightness explain the evening premium the system model misses?

Compares the backcast's hourly gap (actual day-ahead price minus the cost-based model's
price) with how tight supply was: NESO's loss-of-load probability (LoLP) and de-rated
margin from data/scarcity/lolp.csv. Nothing is fitted to prices. The one priced test is
the market's own rule for scarcity, LoLP times the value of lost load (GBP 6,000/MWh),
which sets the reserve scarcity price in cash-out.

Writes data/scarcity/evening_premium_by_margin.csv, _by_hour.csv and _by_year.csv.

Run: uv run openenergy system validate --start 2018-07-01 --end 2025-12-31 --out backcast
     uv run python scripts/evening_premium.py --backcast backcast
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from openenergy.system.validate import mean_daily_spread

DATA = Path(__file__).parents[1] / "data/scarcity"
VOLL = 6000.0
EVENING = range(16, 20)
BANDS = [-np.inf, 2, 4, 6, 8, 10, 15, np.inf]
LABELS = ["under 2", "2-4", "4-6", "6-8", "8-10", "10-15", "over 15"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backcast", type=Path, required=True, help="system validate --out")
    args = parser.parse_args()
    hourly = pd.read_csv(args.backcast / "hourly.csv", index_col=0)
    hourly.index = pd.DatetimeIndex(pd.to_datetime(hourly.index, utc=True))
    tight = pd.read_csv(DATA / "lolp.csv", index_col=0)
    tight.index = pd.DatetimeIndex(pd.to_datetime(tight.index, utc=True))
    tight = tight[["lolp", "derated_margin_mw"]].resample("1h").mean()
    frame = hourly.join(tight).dropna(subset=["price_actual", "price_model", "lolp"])
    frame["gap"] = frame["price_actual"] - frame["price_model"]
    frame["gap_vs_day"] = frame["gap"] - frame.groupby(frame.index.normalize())["gap"].transform(
        "mean"
    )
    frame["scarcity"] = frame["lolp"] * VOLL
    frame["band"] = pd.cut(frame["derated_margin_mw"] / 1000, BANDS, labels=LABELS)

    by_margin = frame.groupby("band", observed=True).agg(
        hours=("gap", "size"),
        gap=("gap", "mean"),
        gap_vs_day=("gap_vs_day", "mean"),
        scarcity=("scarcity", "mean"),
    )
    by_margin.index.name = "derated_margin_gw"
    by_hour = frame.groupby(frame.index.hour).agg(
        gap=("gap", "mean"),
        gap_vs_day=("gap_vs_day", "mean"),
        scarcity=("scarcity", "mean"),
        derated_margin_gw=("derated_margin_mw", lambda s: s.mean() / 1000),
    )
    by_hour.index.name = "utc_hour"
    rows = []
    for year, part in frame.groupby(frame.index.year):
        evening = part[part.index.hour.isin(EVENING)]
        priced = part["price_model"] + part["scarcity"]
        rows.append(
            {
                "year": year,
                "hours": len(part),
                "lolp_hours_share": float((part["lolp"] > 1e-4).mean()),
                "evening_gap_vs_day": float(evening["gap_vs_day"].mean()),
                "evening_scarcity": float(evening["scarcity"].mean()),
                "margin_correlation": float(
                    np.corrcoef(part["gap_vs_day"], -part["derated_margin_mw"])[0, 1]
                ),
                "mae_model": float(part["gap"].abs().mean()),
                "mae_with_scarcity": float((part["price_actual"] - priced).abs().mean()),
                "correlation_model": float(
                    np.corrcoef(part["price_model"], part["price_actual"])[0, 1]
                ),
                "correlation_with_scarcity": float(np.corrcoef(priced, part["price_actual"])[0, 1]),
                "spread_model": mean_daily_spread(part["price_model"]),
                "spread_with_scarcity": mean_daily_spread(priced),
                "spread_actual": mean_daily_spread(part["price_actual"]),
            }
        )
    by_year = pd.DataFrame(rows).set_index("year")
    for name, table in (("margin", by_margin), ("hour", by_hour), ("year", by_year)):
        table.round(3).to_csv(DATA / f"evening_premium_by_{name}.csv")
        print(table.round(2).to_string(), "\n")


if __name__ == "__main__":
    main()
