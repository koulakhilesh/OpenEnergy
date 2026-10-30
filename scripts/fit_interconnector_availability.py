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

Also writes data/system/interconnector_gap_availability.csv: per link and direction, the
share of capacity used by size of the price gap (hourly flows, non-decreasing in the gap),
fitted on 2019-2025, after checking it against the flat factor out of sample in the same
way (both fitted on 2019-2022): energy moved and the hourly correlation with actual flows.

Sources: GB prices from Open Power System Data (to September 2020) and Ember (CC BY 4.0);
neighbour prices from Ember (CC BY 4.0) converted with ECB euro reference rates; flows
from Elexon BMRS FUELHH (contains BMRS data © Elexon Limited copyright and database
right 2026); capacities from the NESO Interconnector Register (NESO Open Data Licence v1.0).

Run: uv run python scripts/fit_interconnector_availability.py
"""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from openenergy.data.ember import gb_prices
from openenergy.data.interconnectors import (
    AVAILABILITY_FILE,
    GAP_EDGES,
    GAP_FILE,
    NEIGHBOUR_FILE,
    REGISTER_FILE,
    NeighbourPriceSource,
    availability_by_gap,
    availability_from_flows,
    interconnector_flows_hourly,
    interconnectors,
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
    check_gap()
    curves = availability_by_gap(SYSTEM, prices(YEARS[0], YEARS[-1]), NEIGHBOURS)
    curves["share"] = curves["share"].round(3)
    curves.to_csv(SYSTEM / GAP_FILE, index=False)
    wide = curves.pivot_table(index=["link", "direction"], columns="gap_from", values="share")
    print(f"\nShare of capacity by price gap (GBP/MWh), fitted on {YEARS[0]}-{YEARS[-1]}:")
    print(wide.round(2).to_string())
    print(f"wrote {SYSTEM / GAP_FILE}")


def prices(first: int, last: int) -> pd.Series:
    return gb_prices(PRICES, date(first, 1, 1), date(last, 12, 31))[0].prices


def check_gap() -> None:
    """Gap curve and flat factor, both fitted on the training years, on every year."""
    curves = availability_by_gap(SYSTEM, prices(TRAIN[0], TRAIN[-1]), NEIGHBOURS)
    flows = interconnector_flows_hourly(SYSTEM)
    fuels = pd.read_csv(SYSTEM / REGISTER_FILE).set_index("link")["bmrs_fuel_type"].str.lower()
    gb = prices(YEARS[0], YEARS[-1])
    index = pd.DatetimeIndex(gb.index)
    edges = np.array(GAP_EDGES)
    rows = []
    for unit in interconnectors(SYSTEM):
        shares = curves[curves["link"] == unit.name]
        if shares.empty or (unit.in_service is not None and unit.in_service.year > TRAIN[-1]):
            continue  # no training years
        live = index >= (unit.in_service if unit.in_service is not None else index[0])
        gap = gb[live] - NEIGHBOURS.prices(unit.neighbour, index[live]).prices
        flow = flows[f"{fuels[unit.name]}_mw"].reindex(gap.index)
        frame = pd.DataFrame({"gap": gap, "flow": flow}).dropna()
        train = frame[frame.index.year.isin(TRAIN)]
        flat = (
            float(train[train.gap > 0].flow.clip(lower=0).mean() / unit.import_mw),
            float((-train[train.gap < 0].flow).clip(lower=0).mean() / unit.export_mw),
        )
        imp = shares[shares["direction"] == "import"].sort_values("gap_from")["share"].to_numpy()
        exp = shares[shares["direction"] == "export"].sort_values("gap_from")["share"].to_numpy()
        bins = np.clip(np.digitize(frame.gap.abs(), edges) - 1, 0, None)
        dearer = frame.gap > 0
        curve = np.where(dearer, imp[bins] * unit.import_mw, -exp[bins] * unit.export_mw)
        level = np.where(dearer, flat[0] * unit.import_mw, -flat[1] * unit.export_mw)
        curve = np.where(frame.gap == 0, 0.0, curve)
        level = np.where(frame.gap == 0, 0.0, level)
        for year in YEARS:
            mask = np.asarray(frame.index.year == year)
            if not mask.any():
                continue
            actual = frame.flow.to_numpy()[mask]
            rows.append(
                {
                    "year": year,
                    "actual_import": actual.clip(min=0).sum(),
                    "gap_import": curve[mask].clip(min=0).sum(),
                    "flat_import": level[mask].clip(min=0).sum(),
                    "actual_export": (-actual).clip(min=0).sum(),
                    "gap_export": (-curve[mask]).clip(min=0).sum(),
                    "flat_export": (-level[mask]).clip(min=0).sum(),
                    "gap_corr": np.corrcoef(actual, curve[mask])[0, 1],
                    "flat_corr": np.corrcoef(actual, level[mask])[0, 1],
                }
            )
    table = pd.DataFrame(rows)
    energy = (
        table.groupby("year")[
            [
                "actual_import",
                "gap_import",
                "flat_import",
                "actual_export",
                "gap_export",
                "flat_export",
            ]
        ].sum()
        / 1e6
    )
    energy[["gap_corr", "flat_corr"]] = table.groupby("year")[["gap_corr", "flat_corr"]].mean()
    print(f"\nBy price gap against flat, both fitted on {TRAIN[0]}-{TRAIN[-1]} (TWh; mean hourly")
    print("correlation with actual flow over links), links in service before 2023:")
    print(energy.round(2).to_string())


if __name__ == "__main__":
    main()
