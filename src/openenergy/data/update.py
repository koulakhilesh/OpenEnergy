"""Download the latest GB day-ahead prices (Ember) and ECB GBP rates."""

from __future__ import annotations

import csv
import io
import os
import time
import urllib.request
import zipfile
from pathlib import Path

EMBER_HOURLY = (
    "https://files.ember-energy.org/public-downloads/price/outputs/"
    "european_wholesale_electricity_price_data_hourly.zip"
)
EMBER_MEMBER = "United Kingdom.csv"
ECB_DAILY = (
    "https://data-api.ecb.europa.eu/service/data/EXR/D.GBP.EUR.SP00.A"
    "?startPeriod=2016-06-01&format=csvdata"
)
PRICE_FILE = "gb_day_ahead_ember.csv"
RATE_FILE = "ecb_gbp_per_eur.csv"


def cache_dir() -> Path:
    """``$XDG_CACHE_HOME/openenergy/prices``, defaulting to ``~/.cache/openenergy/prices``."""
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "openenergy" / "prices"


def update_prices(directory: str | Path) -> tuple[Path, int, str, str]:
    """Write Ember hourly UK prices (EUR, unchanged) and ECB daily GBP rates to ``directory``.

    Returns the price file, its number of hours and the first and last UTC hour.
    """
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    archive = zipfile.ZipFile(io.BytesIO(_download(EMBER_HOURLY)))
    name = next((n for n in archive.namelist() if n.endswith(EMBER_MEMBER)), None)
    if name is None:
        raise OSError(f"{EMBER_MEMBER} not found in the Ember archive")
    with archive.open(name) as handle:
        rows = list(csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8")))
    if not rows:
        raise OSError("the Ember UK file is empty")
    prices = out / PRICE_FILE
    with prices.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["utc_timestamp", "price_eur_per_mwh"])
        for row in rows:
            writer.writerow(
                [row["Datetime (UTC)"].replace(" ", "T") + "Z", row["Price (EUR/MWhe)"]]
            )
    records = list(csv.DictReader(io.StringIO(_download(ECB_DAILY).decode())))
    with (out / RATE_FILE).open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "gbp_per_eur"])
        for record in sorted(records, key=lambda r: r["TIME_PERIOD"]):
            writer.writerow([record["TIME_PERIOD"], record["OBS_VALUE"]])
    return prices, len(rows), rows[0]["Datetime (UTC)"], rows[-1]["Datetime (UTC)"]


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "openenergy"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return bytes(response.read())
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")
