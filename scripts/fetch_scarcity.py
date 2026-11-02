"""Fetch how tight GB's supply was: loss-of-load probability and de-rated margin, into
data/scarcity/.

Elexon BMRS (BMRS data licence; contains BMRS data (c) Elexon Limited copyright and
database right 2026) publishes NESO's loss-of-load probability (LoLP) and de-rated margin
(MW) for each settlement period at a few horizons up to about 12 hours ahead, revised up to
delivery. For each settlement period this keeps the last value published before it
started, the one cash-out uses for the reserve scarcity price (LoLP x VoLL). It is an
outturn-like input, as the system model's demand and wind are, not a day-ahead forecast.

Writes lolp.csv: utc_timestamp (start of the half-hour), lolp, derated_margin_mw,
published (when that value was issued).

Run: uv run python scripts/fetch_scarcity.py
"""

import argparse
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

OUT = Path(__file__).parents[1] / "data/scarcity"
API = "https://data.elexon.co.uk/bmrs/api/v1/datasets/LOLPDRM/stream"


def get(url: str) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "OpenEnergy"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body: list[dict] = json.load(response)
                return body
        except OSError:
            if attempt == 4:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def for_day(day: date) -> pd.DataFrame:
    before = day - timedelta(days=1)
    rows = get(f"{API}?publishDateTimeFrom={before}T12:00Z&publishDateTimeTo={day}T23:59Z")
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    start = pd.to_datetime(frame["startTime"], utc=True)
    published = pd.to_datetime(frame["publishTime"], utc=True)
    keep = (start.dt.date == day) & (published <= start)
    frame = frame[keep].assign(start=start[keep], issued=published[keep])
    frame = frame.sort_values("issued").drop_duplicates("start", keep="last")
    return pd.DataFrame(
        {
            "utc_timestamp": frame["start"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lolp": frame["lossOfLoadProbability"],
            "derated_margin_mw": frame["deratedMargin"].round(1),
            "published": frame["publishTime"],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, default=date(2018, 7, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 30))
    args = parser.parse_args()
    days = pd.date_range(args.start, args.end - timedelta(days=1)).date
    with ThreadPoolExecutor(8) as pool:
        frames = [f for f in pool.map(for_day, days) if not f.empty]
    table = pd.concat(frames).sort_values("utc_timestamp")
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "lolp.csv", index=False)
    first, last = table["utc_timestamp"].iloc[0], table["utc_timestamp"].iloc[-1]
    print(f"lolp.csv: {len(table)} half-hours, {first} to {last}")


if __name__ == "__main__":
    main()
