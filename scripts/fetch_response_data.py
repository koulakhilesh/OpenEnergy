"""Download GB dynamic frequency response prices and derive monthly utilisation into data/response/.

Sources (National Energy System Operator, NESO Open Data Licence v1.0,
https://www.neso.energy/data-portal/neso-open-licence; OpenEnergy is not affiliated with or
endorsed by NESO):

- Dynamic Containment, Regulation and Moderation auction results, "Results Summary Master
  Data 2021-2023", https://www.neso.energy/data-portal/dynamic-containment-data (delivery
  times in UK local time).
- Enduring Auction Capability (EAC) auction results, results summaries (FY archives and
  current), https://www.neso.energy/data-portal/eac-auction-results (delivery times in UTC).
- System frequency data, one-second GB frequency per month,
  https://www.neso.energy/data-portal/system-frequency-data (with --utilisation; about
  75 MB per month, files are read and discarded).

Writes one row per delivery block with each service's clearing price (GBP/MW/h) and
cleared volume (MW), and one row per month with the average fraction of contracted MW each
service delivers (= MWh per MW per hour), from the service response envelopes.

Run: uv run python scripts/fetch_response_data.py [--utilisation] [--from 2021-09]
"""

import argparse
import calendar
import csv
import io
import json
import re
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd

from openenergy.data.response import PRICES_FILE, SERVICES, UTILISATION_FILE, utilisation
from openenergy.data.update import _download

OUTPUT = Path(__file__).parents[1] / "data/response"
API = "https://api.neso.energy/api/3/action/datapackage_show?id={}"
MONTHS = {calendar.month_name[number].lower(): number for number in range(1, 13)}


def resources(dataset: str) -> Iterator[tuple[str, str]]:
    for resource in json.loads(_download(API.format(dataset)))["result"]["resources"]:
        yield str(resource.get("name", "")), str(resource["path"])


def master_2021_2023() -> pd.DataFrame:
    path = next(
        url
        for name, url in resources("dynamic-containment-data")
        if "results_summary" in name and "2021-2023" in name
    )
    frame = pd.read_csv(io.BytesIO(_download(path)))
    london = "Europe/London"
    return pd.DataFrame(
        {
            "service": frame["Service"],
            "start": pd.to_datetime(frame["Delivery Start"])
            .dt.tz_localize(london)
            .dt.tz_convert("UTC"),
            "end": pd.to_datetime(frame["Delivery End"])
            .dt.tz_localize(london)
            .dt.tz_convert("UTC"),
            "price": frame["Clearing Price"],
            "mw": frame["Cleared Volume"],
        }
    )


def eac() -> pd.DataFrame:
    frames = []
    for name, url in resources("eac-auction-results"):
        summary = "results_summary" in name and "daily" not in name
        if not summary:
            continue
        frame = pd.read_csv(io.BytesIO(_download(url)))
        frame = frame[frame["serviceType"] == "Response"]
        frames.append(
            pd.DataFrame(
                {
                    "service": frame["auctionProduct"],
                    "start": pd.to_datetime(frame["deliveryStart"]).dt.tz_localize("UTC"),
                    "end": pd.to_datetime(frame["deliveryEnd"]).dt.tz_localize("UTC"),
                    "price": frame["clearingPrice"],
                    "mw": frame["clearedVolume"],
                }
            )
        )
    return pd.concat(frames)


def write_prices() -> None:
    rows = pd.concat([master_2021_2023(), eac()])
    rows = rows[rows["service"].isin(list(SERVICES))]
    # EAC replaced the old auctions in November 2023; it wins where both list a block.
    rows = rows.drop_duplicates(["service", "start"], keep="last")
    wide = rows.pivot_table(index=["start", "end"], columns="service", values=["price", "mw"])
    out = pd.DataFrame(index=wide.index)
    for name in SERVICES:
        out[f"{name.lower()}_gbp_per_mw_h"] = wide[("price", name)]
        out[f"{name.lower()}_mw"] = wide[("mw", name)]
    out = out.reset_index().sort_values("start")
    stamp = "%Y-%m-%dT%H:%M:%SZ"
    out.insert(0, "utc_start", out.pop("start").dt.strftime(stamp))
    out.insert(1, "utc_end", out.pop("end").dt.strftime(stamp))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT / PRICES_FILE, index=False, float_format="%.6g")
    print(
        f"{PRICES_FILE}: {len(out)} blocks, {out['utc_start'].iloc[0]} to {out['utc_end'].iloc[-1]}"
    )


def write_utilisation(first: pd.Period) -> None:
    months: dict[pd.Period, str] = {}
    for name, url in resources("system-frequency-data"):
        match = re.match(r"([a-z]+)_(\d{4})", name)
        if match and match.group(1) in MONTHS:
            month = pd.Period(year=int(match.group(2)), month=MONTHS[match.group(1)], freq="M")
            if month >= first:
                months[month] = url
    path = OUTPUT / UTILISATION_FILE
    done: dict[str, list[str]] = {}
    if path.is_file():
        with path.open() as handle:
            done = {row[0]: row for row in csv.reader(handle)}
    header = ["month", *(name.lower() for name in SERVICES), "samples"]
    for month, url in sorted(months.items()):
        key = f"{month}-01"
        if key in done:
            continue
        compression = "zip" if url.endswith(".zip") else None
        frame = pd.read_csv(io.BytesIO(_download(url)), compression=compression)
        values = pd.to_numeric(frame.iloc[:, 1], errors="coerce").to_numpy(dtype=np.float64)
        frequency = values.copy()
        # Outside 49-51 Hz would be a GB blackout-scale event; treat as bad samples.
        frequency[(frequency < 49) | (frequency > 51)] = np.nan
        factors = utilisation(frequency)
        done[key] = [
            key,
            *(f"{factors[n]:.6f}" for n in SERVICES),
            str(np.isfinite(frequency).sum()),
        ]
        print(month, done[key][1:], flush=True)
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(row for key, row in sorted(done.items()) if key != "month")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--utilisation", action="store_true", help="also derive utilisation")
    parser.add_argument("--from", dest="first", default="2021-09", type=pd.Period)
    args = parser.parse_args()
    write_prices()
    if args.utilisation:
        write_utilisation(args.first)


if __name__ == "__main__":
    main()
