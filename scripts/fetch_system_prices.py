"""Download GB system (imbalance) prices from Elexon's BMRS Insights API into data/balancing/.

Source: Elexon, BMRS Insights API, settlement system prices (dataset DISEBSP),
https://bmrs.elexon.co.uk/ (API: https://data.elexon.co.uk/bmrs/api/v1). Reused under the
BMRS data licence, https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/.
Contains BMRS data © Elexon Limited copyright and database right 2026. OpenEnergy is not
affiliated with or endorsed by Elexon.

GB has a single imbalance price since November 2015 (system sell price = system buy price),
so one price per settlement period is written, unchanged.

Run: uv run python scripts/fetch_system_prices.py [--start 2016-01-01] [--end 2025-12-31]
"""

import argparse
import concurrent.futures
import csv
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from openenergy.data.update import _download

API = "https://data.elexon.co.uk/bmrs/api/v1/balancing/settlement/system-prices/{day}?format=json"
OUTPUT = Path(__file__).parents[1] / "data/balancing/gb_system_prices.csv"


def fetch(day: date) -> list[tuple[str, float]]:
    rows = []
    for record in json.loads(_download(API.format(day=day.isoformat())))["data"]:
        if record["systemSellPrice"] != record["systemBuyPrice"]:
            raise ValueError(f"sell and buy prices differ: {record}")
        rows.append((str(record["startTime"]), float(record["systemSellPrice"])))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=date.fromisoformat, default=date(2016, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 12, 31))
    args = parser.parse_args()
    days = [args.start + timedelta(days=i) for i in range((args.end - args.start).days + 1)]
    prices: dict[str, float] = {}
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        for rows in pool.map(fetch, days):
            prices.update(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    first = datetime.combine(args.start, datetime.min.time(), UTC)
    last = datetime.combine(args.end + timedelta(days=1), datetime.min.time(), UTC)
    absent = 0
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["utc_timestamp", "system_price_gbp_per_mwh"])
        # Every half-hour is written; ones the API did not return are left blank.
        cursor = first
        while cursor < last:
            stamp = cursor.strftime("%Y-%m-%dT%H:%M:%SZ")
            absent += stamp not in prices
            writer.writerow([stamp, prices.get(stamp, "")])
            cursor += timedelta(minutes=30)
    print(f"wrote {len(prices)} settlement periods ({absent} not returned, left blank) to {OUTPUT}")


if __name__ == "__main__":
    main()
