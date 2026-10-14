"""Fit each interconnector's import and export availability from its actual flows.

A price taker on actual GB day-ahead prices imports at full capacity whenever GB is dearer
than the neighbour and exports whenever it is cheaper. Real links trade much less: they
have outages, ramp limits, losses, capacity sold ahead and flows that follow intraday and
balancing prices. Each link's availability is its actual energy over that price taker's,
per direction, capped at 1; links with no trade in the fitting years get the fleet mean.
Only actual prices and flows are used, never modelled prices.

Writes data/system/interconnector_availability.csv, fitted on every complete year from
2019 (the first with Irish prices) to 2025, and first prints an out-of-sample check:
factors fitted on 2019-2022 applied to 2023-2025.

Sources: GB prices from Open Power System Data (to September 2020) and Ember (CC BY 4.0);
neighbour prices from Ember (CC BY 4.0) converted with ECB euro reference rates; flows
from Elexon BMRS FUELHH (contains BMRS data © Elexon Limited copyright and database
right 2026); capacities from the NESO Interconnector Register (NESO Open Data Licence v1.0).

Run: uv run python scripts/fit_interconnector_availability.py
"""

from datetime import date
from pathlib import Path

import pandas as pd

from openenergy.data.ember import gb_prices
from openenergy.data.interconnectors import (
    AVAILABILITY_FILE,
    NEIGHBOUR_FILE,
    NeighbourPriceSource,
    availability_from_flows,
)

ROOT = Path(__file__).parents[1]
SYSTEM = ROOT / "data/system"
PRICES = [
    ROOT / "data/time_series/time_series_60min_singleindex_filtered.csv",
    ROOT / "data/prices/gb_day_ahead_ember.csv",
]
NEIGHBOURS = NeighbourPriceSource(ROOT / "data/prices" / NEIGHBOUR_FILE)
YEARS = range(2019, 2026)
TRAIN, TEST = range(2019, 2023), range(2023, 2026)


def fit(first: int, last: int) -> pd.DataFrame:
    prices = gb_prices(PRICES, date(first, 1, 1), date(last, 12, 31))[0].prices
    return availability_from_flows(SYSTEM, prices, NEIGHBOURS)


def check() -> None:
    factors = fit(TRAIN[0], TRAIN[-1])
    print(f"Out-of-sample check: fitted on {TRAIN[0]}-{TRAIN[-1]} (TWh)")
    print("year  set    imports full/fitted/actual    exports full/fitted/actual")
    for year in (*TRAIN, *TEST):
        trade = fit(year, year)
        row = {}
        for direction in ("import", "export"):
            full = trade[f"price_taker_{direction}_mwh"]
            fitted = full * factors[f"{direction}_availability"]
            row[direction] = (
                full.sum() / 1e6,
                fitted.sum() / 1e6,
                trade[f"actual_{direction}_mwh"].sum() / 1e6,
            )
        tag = "train" if year in TRAIN else "test"
        imports = " / ".join(f"{v:5.1f}" for v in row["import"])
        exports = " / ".join(f"{v:5.1f}" for v in row["export"])
        print(f"{year}  {tag:5s}  {imports}    {exports}")


def main() -> None:
    check()
    table = fit(YEARS[0], YEARS[-1])
    columns = ["import_availability", "export_availability"]
    out = table[columns].round(3).reset_index()
    out.to_csv(SYSTEM / AVAILABILITY_FILE, index=False)
    print(f"\nFitted on {YEARS[0]}-{YEARS[-1]}:")
    print(out.to_string(index=False))
    print(f"wrote {SYSTEM / AVAILABILITY_FILE}")


if __name__ == "__main__":
    main()
