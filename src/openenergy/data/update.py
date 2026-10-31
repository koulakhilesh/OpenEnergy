"""Download the latest GB day-ahead prices (Ember), ECB GBP rates and forecast inputs."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import time
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd

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
NEIGHBOUR_FILE = "europe_day_ahead_ember.csv"
# Markets GB has interconnectors to, as Ember names its country files.
NEIGHBOURS = ("France", "Netherlands", "Belgium", "Norway", "Denmark", "Ireland")
NEIGHBOURS_FROM = "2015-01-01"
ONS_SAP = (
    "https://www.ons.gov.uk/economy/economicoutputandproductivity/output/datasets/"
    "systemaveragepricesapofgas"
)
SAP_SHEET = "1.Daily SAP Gas"
NESO_PACKAGE = "https://api.neso.energy/api/3/action/datapackage_show?id={id}"
NESO_DEMAND = ("1-day-ahead-demand-forecast", "historic_day_ahead_demand_forecasts")
WINDFOR = (
    "https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream"
    "?publishDateTimeFrom={start}T00:00Z&publishDateTimeTo={end}T00:00Z"
)
WINDFOR_FROM = date(2018, 1, 1)
# Forecasts kept for the plan made at noon UTC the day before (the backtest default).
DECISION_LEAD = pd.Timedelta(hours=12)
GAS_FILE = "gas_sap_daily.csv"
DEMAND_FILE = "neso_demand_day_ahead.csv"
WIND_FILE = "elexon_wind_day_ahead.csv"
_XLSX = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


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
    _write_neighbours(archive, out / NEIGHBOUR_FILE)
    return prices, len(rows), rows[0]["Datetime (UTC)"], rows[-1]["Datetime (UTC)"]


def _write_neighbours(archive: zipfile.ZipFile, path: Path) -> None:
    """Hourly EUR prices of GB's interconnected neighbours, one column each, unchanged."""
    columns: dict[str, dict[str, str]] = {}
    for country in NEIGHBOURS:
        name = next((n for n in archive.namelist() if n.endswith(f"{country}.csv")), None)
        if name is None:
            raise OSError(f"{country}.csv not found in the Ember archive")
        with archive.open(name) as handle:
            reader = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8"))
            columns[country] = {
                row["Datetime (UTC)"]: row["Price (EUR/MWhe)"]
                for row in reader
                if row["Datetime (UTC)"] >= NEIGHBOURS_FROM
            }
    stamps = sorted(set().union(*columns.values()))
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["utc_timestamp", *(c.lower() for c in NEIGHBOURS)])
        for stamp in stamps:
            values = [columns[c].get(stamp, "") for c in NEIGHBOURS]
            writer.writerow([stamp.replace(" ", "T") + "Z", *values])


def update_fundamentals(
    directory: str | Path, end: date | None = None
) -> list[tuple[str, int, str, str]]:
    """Write the daily gas price, NESO's day-ahead demand forecast and Elexon's wind forecast.

    Returns (file name, rows, first, last) for each file written.
    """
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    gas = _sap_daily()
    gas.to_csv(out / GAS_FILE, index=False)
    written.append((GAS_FILE, len(gas), gas["date"].iloc[0], gas["date"].iloc[-1]))
    demand = _neso_demand(pd.read_csv(io.BytesIO(_download(_neso_resource(*NESO_DEMAND)))))
    demand.to_csv(out / DEMAND_FILE, index=False)
    written.append((DEMAND_FILE, len(demand), demand.iloc[0, 0], demand.iloc[-1, 0]))
    wind = _windfor(WINDFOR_FROM, end or date.today())
    wind.to_csv(out / WIND_FILE, index=False)
    written.append((WIND_FILE, len(wind), wind.iloc[0, 0], wind.iloc[-1, 0]))
    return written


def _sap_daily() -> pd.DataFrame:
    """ONS's daily System Average Price of gas, p/kWh, from its latest workbook."""
    page = _download(ONS_SAP).decode("utf-8", "replace")
    links = re.findall(
        r'/file\?uri=(/economy/[^"]*?systemaveragepricesapofgas/(\d{4})/[^"]+?\.xlsx)', page
    )
    if not links:
        raise OSError("no SAP workbook link found on the ONS dataset page")
    # The page also links a "current" alias, which is not downloadable; take the newest edition.
    latest = max(links, key=lambda link: link[1])[0]
    rows = _xlsx_rows(_download("https://www.ons.gov.uk/file?uri=" + latest), SAP_SHEET)
    header = next(i for i, row in enumerate(rows) if row and row[0] == "Date")
    records = []
    for row in rows[header + 1 :]:
        if len(row) < 2 or not row[0] or not _is_number(row[1]):
            continue
        day = date(1899, 12, 30) + timedelta(days=int(float(row[0])))
        records.append((day.isoformat(), round(float(row[1]), 4)))
    if not records:
        raise OSError("the ONS SAP workbook has no daily prices")
    return pd.DataFrame(records, columns=["date", "sap_p_per_kwh"])


def _neso_resource(dataset: str, resource: str) -> str:
    package = json.loads(_download(NESO_PACKAGE.format(id=dataset)))
    for item in package["result"]["resources"]:
        if item["name"] == resource:
            return str(item["path"])
    raise OSError(f"NESO dataset {dataset} has no resource {resource}")


def _neso_demand(frame: pd.DataFrame) -> pd.DataFrame:
    """Day-ahead cardinal points: UTC time (middle of each point's window), MW, issue time.

    NESO gives each point's window in UK clock time (HHMM); points inside the autumn
    clock-change hour are ambiguous and dropped.
    """
    frame = frame[frame["DAYSAHEAD"] == 1]
    start, end = frame["CP_ST_TIME"], frame["CP_END_TIME"]
    minutes = (start // 100 * 60 + start % 100 + end // 100 * 60 + end % 100) / 2
    local = pd.to_datetime(frame["TARGETDATE"]) + pd.to_timedelta(minutes, unit="min")
    target = local.dt.tz_localize(
        "Europe/London", ambiguous="NaT", nonexistent="shift_forward"
    ).dt.tz_convert("UTC")
    out = pd.DataFrame(
        {
            "target_utc": target,
            "demand_mw": frame["FORECASTDEMAND"],
            "issued_utc": pd.to_datetime(frame["FORECAST_TIMESTAMP"], utc=True),
        }
    ).dropna()
    out = out.sort_values(["target_utc", "issued_utc"]).drop_duplicates(
        ["target_utc", "issued_utc"], keep="last"
    )
    return _iso(out, ["target_utc", "issued_utc"])


def _windfor(start: date, end: date) -> pd.DataFrame:
    """Hourly wind forecast for each hour from the latest issue by noon UTC the day before."""
    rows: list[dict[str, object]] = []
    for first in pd.date_range(start, end, freq="MS"):
        last = first + pd.offsets.MonthBegin(1)
        url = WINDFOR.format(start=first.date(), end=last.date())
        rows += json.loads(_download(url))
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise OSError("Elexon returned no wind forecasts")
    target = pd.to_datetime(frame["startTime"], utc=True)
    issued = pd.to_datetime(frame["publishTime"], utc=True)
    frame = frame.assign(target_utc=target, issued_utc=issued)
    frame = frame[issued <= target.dt.normalize() - DECISION_LEAD]
    frame = frame.sort_values("issued_utc").drop_duplicates("target_utc", keep="last")
    out = frame.sort_values("target_utc")[["target_utc", "generation", "issued_utc"]]
    out = out.rename(columns={"generation": "wind_mw"})
    return _iso(out, ["target_utc", "issued_utc"])


def _iso(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    frame = frame.copy()
    for column in columns:
        frame[column] = frame[column].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return frame.reset_index(drop=True)


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _xlsx_rows(content: bytes, sheet: str) -> list[list[str]]:
    """Cell values of one worksheet as strings, without a spreadsheet library."""
    book = zipfile.ZipFile(io.BytesIO(content))
    workbook = ElementTree.fromstring(book.read("xl/workbook.xml"))
    rel_id = next(
        s.attrib[_REL]
        for s in workbook.iterfind("m:sheets/m:sheet", _XLSX)
        if s.attrib["name"] == sheet
    )
    rels = ElementTree.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    target = next(r.attrib["Target"] for r in rels if r.attrib["Id"] == rel_id)
    path = target.lstrip("/") if target.startswith("/") else "xl/" + target
    shared: list[str] = []
    if "xl/sharedStrings.xml" in book.namelist():
        strings = ElementTree.fromstring(book.read("xl/sharedStrings.xml"))
        shared = ["".join(t.text or "" for t in si.iter(f"{{{_XLSX['m']}}}t")) for si in strings]
    rows = []
    for row in ElementTree.fromstring(book.read(path)).iterfind("m:sheetData/m:row", _XLSX):
        values = []
        for cell in row.iterfind("m:c", _XLSX):
            raw = cell.find("m:v", _XLSX)
            text = "" if raw is None or raw.text is None else raw.text
            if cell.attrib.get("t") == "s" and text:
                text = shared[int(text)]
            elif cell.attrib.get("t") == "inlineStr":
                text = "".join(t.text or "" for t in cell.iter(f"{{{_XLSX['m']}}}t"))
            values.append(text)
        rows.append(values)
    return rows


def _download(url: str) -> bytes:
    # ONS answers 429 to requests without an Accept header.
    request = urllib.request.Request(url, headers={"User-Agent": "openenergy", "Accept": "*/*"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return bytes(response.read())
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")
