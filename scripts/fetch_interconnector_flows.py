"""Download GB interconnector flows from Elexon BMRS (FUELHH): daily totals and hourly flows.

Source: Elexon, BMRS Insights API, half-hourly generation by fuel type (dataset FUELHH),
https://bmrs.elexon.co.uk/, reused under the BMRS data licence,
https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/.
Contains BMRS data © Elexon Limited copyright and database right 2026. OpenEnergy is not
affiliated with or endorsed by Elexon.

FUELHH reports each interconnector's flow (MW, positive into GB). This writes, per UTC
day, the energy imported and exported on each link (MWh), used to date when each link
entered service and to check the system model's flows; and, from 2019 (the first year
with every neighbour's price), each link's hourly net flow (MW, the mean of its two
half-hours), used to fit how much of a price gap each link trades.

Run: uv run python scripts/fetch_interconnector_flows.py [--start 2016-01-01] [--end 2026-10-29]
"""

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from openenergy.data.update import _download

API = (
    "https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream"
    "?settlementDateFrom={start}&settlementDateTo={end}"
)
OUTPUT = Path(__file__).parents[1] / "data/system/interconnector_flows.csv"
HOURLY = Path(__file__).parents[1] / "data/system/interconnector_flows_hourly.csv"
HOURLY_FROM = pd.Timestamp("2019-01-01", tz="UTC")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=date.fromisoformat, default=date(2016, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 29))
    args = parser.parse_args()
    rows = []
    for first in pd.date_range(args.start, args.end, freq="MS"):
        last = min(first + pd.offsets.MonthEnd(0), pd.Timestamp(args.end))
        url = API.format(start=first.date(), end=last.date())
        rows += [r for r in json.loads(_download(url)) if r["fuelType"].startswith("INT")]
        print(first.strftime("%Y-%m"), len(rows), flush=True)
    frame = pd.DataFrame(rows)
    frame["start"] = pd.to_datetime(frame["startTime"], utc=True)
    frame = frame.drop_duplicates(["fuelType", "start"], keep="last")
    window = (frame["start"] >= pd.Timestamp(args.start, tz="UTC")) & (
        frame["start"] < pd.Timestamp(args.end, tz="UTC") + pd.Timedelta(days=1)
    )
    frame = frame[window]
    frame["day"] = frame["start"].dt.strftime("%Y-%m-%d")
    mwh = frame["generation"] * 0.5
    frame["import_mwh"] = mwh.clip(lower=0)
    frame["export_mwh"] = (-mwh).clip(lower=0)
    daily = frame.pivot_table(
        index="day", columns="fuelType", values=["import_mwh", "export_mwh"], aggfunc="sum"
    )
    daily.columns = [f"{fuel.lower()}_{kind}" for kind, fuel in daily.columns]
    # FUELHH lists some fuel types (e.g. INTELE) that never carry flow; leave them out.
    moved = daily.fillna(0).T.groupby(lambda c: c.rsplit("_", 2)[0]).sum().T.sum()
    daily = daily[[c for c in daily.columns if moved[c.rsplit("_", 2)[0]] > 0]]
    daily = daily[sorted(daily.columns)].round(1)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(OUTPUT, index_label="date")
    print(f"wrote {len(daily)} days, {len(daily.columns) // 2} links to {OUTPUT}")
    links = sorted({c.rsplit("_", 2)[0].upper() for c in daily.columns})
    recent = frame[frame["start"] >= HOURLY_FROM]
    hourly = recent.pivot_table(
        index=recent["start"].dt.floor("h"), columns="fuelType", values="generation"
    )[links]
    hourly.columns = [f"{fuel.lower()}_mw" for fuel in hourly.columns]
    hourly.index = hourly.index.strftime("%Y-%m-%dT%H:%M:%SZ")
    hourly.round(0).to_csv(HOURLY, index_label="utc_timestamp", float_format="%.0f")
    print(f"wrote {len(hourly)} hours to {HOURLY}")


if __name__ == "__main__":
    main()
