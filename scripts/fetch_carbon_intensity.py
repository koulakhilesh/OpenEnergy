"""Download GB national carbon intensity from NESO's Carbon Intensity API.

Source: National Energy System Operator (NESO), Carbon Intensity API,
https://carbonintensity.org.uk/ (API docs: https://carbon-intensity.github.io/api-definitions/).
Licence: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/; terms of use:
https://github.com/carbon-intensity/terms. Writes half-hourly forecast and actual gCO2/kWh
unchanged. OpenEnergy is not affiliated with or endorsed by NESO.

Run: uv run python scripts/fetch_carbon_intensity.py [--start 2018-01-01] [--end 2025-12-31]
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
HALF_HOUR = timedelta(minutes=30)


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
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 12, 31))
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
    absent = 0
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["utc_timestamp", "forecast", "actual"])
        # Every half-hour is written; ones the API did not return are left blank.
        cursor = first
        while cursor < last:
            timestamp = cursor.strftime("%Y-%m-%dT%H:%M:%SZ")
            forecast, actual = rows.get(timestamp, (None, None))
            absent += timestamp not in rows
            writer.writerow([timestamp, *("" if v is None else v for v in (forecast, actual))])
            cursor += HALF_HOUR
    print(f"wrote {len(rows)} half-hours ({absent} not returned, left blank) to {OUTPUT}")


if __name__ == "__main__":
    main()
