"""Download GB national carbon intensity from NESO's Carbon Intensity API.

Data: National Energy System Operator, Carbon Intensity API, CC BY 4.0,
https://carbonintensity.org.uk/. Writes half-hourly forecast and actual gCO2/kWh.

Run: uv run python scripts/fetch_carbon_intensity.py [--start 2018-01-01] [--end 2020-09-30]
"""

import argparse
import csv
import json
import time
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

API = "https://api.carbonintensity.org.uk/intensity/{start}/{end}"
OUTPUT = Path(__file__).parents[1] / "data/carbon_intensity/gb_national.csv"
# The API returns at most 14 days per request.
WINDOW = timedelta(days=14)


def fetch(start: datetime, end: datetime) -> list[dict[str, object]]:
    url = API.format(start=start.strftime("%Y-%m-%dT%H:%MZ"), end=end.strftime("%Y-%m-%dT%H:%MZ"))
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                payload = json.load(response)
            return list(payload["data"])
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2020, 9, 30))
    args = parser.parse_args()

    first = datetime.combine(args.start, datetime.min.time(), UTC)
    last = datetime.combine(args.end + timedelta(days=1), datetime.min.time(), UTC)
    rows: dict[str, tuple[object, object]] = {}
    cursor = first
    while cursor < last:
        stop = min(cursor + WINDOW, last)
        for record in fetch(cursor, stop):
            timestamp = datetime.fromisoformat(str(record["from"]).replace("Z", "+00:00"))
            if first <= timestamp < last:
                intensity = record["intensity"]
                if not isinstance(intensity, dict):
                    raise ValueError(f"unexpected intensity record: {record}")
                rows[timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")] = (
                    intensity.get("forecast"),
                    intensity.get("actual"),
                )
        cursor = stop

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["utc_timestamp", "forecast", "actual"])
        for timestamp in sorted(rows):
            forecast, actual = rows[timestamp]
            writer.writerow([timestamp, *("" if v is None else v for v in (forecast, actual))])
    print(f"wrote {len(rows)} half-hours to {OUTPUT}")


if __name__ == "__main__":
    main()
