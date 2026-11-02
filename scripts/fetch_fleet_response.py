"""Fetch the frequency response (and reserve) contracts GB's battery units won into data/fleet/.

NESO publishes the result of every response auction by unit (NESO Open Data Licence v1.0):
the Dynamic Containment, Regulation and Moderation day-ahead auctions from September 2021
to November 2023 ("DC, DR & DM Results By Unit Master Data 2021-2023") and the Enduring
Auction Capability from November 2023 ("NESO Response-Reserve Results By Unit", one file
per financial year plus the current one). Auction units are BM unit ids, so the battery
units in data/fleet/battery_units.csv are matched by their National Grid id.

Writes battery_response_daily.csv: for each unit, UTC day and product, the contracted
availability (MW x hours) and its value at the clearing price (GBP). Cancelled contracts
are left out. Delivery times in the files are UK local time.

Run: uv run python scripts/fetch_fleet_response.py
"""

import io
import json
import urllib.request
from pathlib import Path

import pandas as pd

OUT = Path(__file__).parents[1] / "data/fleet"
API = "https://api.neso.energy/api/3/action/package_show?id="


def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "OpenEnergy", "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return bytes(response.read())


def files(dataset: str, keep: str, skip: str = "Daily") -> list[pd.DataFrame]:
    out = []
    for resource in json.loads(get(API + dataset))["result"]["resources"]:
        if keep in resource["name"] and skip not in resource["name"]:
            out.append(pd.read_csv(io.BytesIO(get(resource["url"])), low_memory=False))
    return out


def utc(local: pd.Series) -> pd.Series:
    times = pd.to_datetime(local, format="ISO8601")
    if times.dt.tz is not None:
        return times.dt.tz_convert("UTC")
    return times.dt.tz_localize(
        "Europe/London", ambiguous="NaT", nonexistent="shift_forward"
    ).dt.tz_convert("UTC")


def main() -> None:
    units = pd.read_csv(OUT / "battery_units.csv")
    by_ng = dict(zip(units["national_grid_unit"], units["unit"], strict=True))

    (early,) = files("dynamic-containment-data", "Results By Unit")
    early = early[
        early["Cancelled"].isna()
        | (early["Cancelled"].astype(str).str.lower().isin(["false", "no", "0", ""]))
    ]
    early = pd.DataFrame(
        {
            "ng_unit": early["Unit Name"],
            "product": early["Service"],
            "mw": early["Cleared Volume"],
            "price": early["Clearing Price"],
            "start": utc(early["Delivery Start"]),
            "end": utc(early["Delivery End"]),
        }
    )
    later = pd.concat(files("eac-auction-results", "Results By Unit"))
    later = later.drop_duplicates(["auctionUnit", "auctionProduct", "deliveryStart"])
    later = pd.DataFrame(
        {
            "ng_unit": later["auctionUnit"],
            "product": later["auctionProduct"],
            "mw": later["executedQuantity"],
            "price": later["clearingPrice"],
            "start": utc(later["deliveryStart"]),
            "end": utc(later["deliveryEnd"]),
        }
    )
    # The EAC files start in November 2023, where the day-ahead DC auctions stop.
    first_eac = later["start"].min()
    frame = pd.concat([early[early["start"] < first_eac], later]).dropna(subset=["start", "end"])
    frame = frame[frame["ng_unit"].isin(by_ng) & (frame["mw"] > 0)]
    hours = (frame["end"] - frame["start"]).dt.total_seconds() / 3600
    daily = pd.DataFrame(
        {
            "date": frame["start"].dt.strftime("%Y-%m-%d"),
            "unit": frame["ng_unit"].map(by_ng),
            "product": frame["product"],
            "mw_hours": frame["mw"] * hours,
            "gbp": frame["mw"] * hours * frame["price"],
        }
    )
    daily = (
        daily.groupby(["date", "unit", "product"], as_index=False)[["mw_hours", "gbp"]]
        .sum()
        .round(3)
    )
    daily.to_csv(OUT / "battery_response_daily.csv", index=False)
    print(
        f"battery_response_daily.csv: {len(daily)} rows, {daily['unit'].nunique()} units, "
        f"{daily['date'].min()} to {daily['date'].max()}"
    )


if __name__ == "__main__":
    main()
