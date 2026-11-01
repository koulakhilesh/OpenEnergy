"""Fetch the data for GB's two zones, Scotland and England & Wales, into data/zones/.

- demand_by_zone.csv: each UTC half-hour from 2019, national demand (ND), England and
  Wales demand and their difference (Scotland), the transfer from Scotland to England
  (NESO's SCOTTISH_TRANSFER, the flow across the B6 boundary) and embedded wind and solar
  generation and capacity, MW. Source: NESO, Historic Demand Data, one file per year,
  https://www.neso.energy/data-portal/historic-demand-data, NESO Open Data Licence v1.0.
  Changes: settlement date and period turned into UTC times; other columns dropped.
- capacity_by_year.csv: grid-scale capacity in operation at the end of each year by
  technology and zone (Scotland or England and Wales), MW, from DESNZ's Renewable Energy
  Planning Database (REPD), July 2026 extract,
  https://www.gov.uk/government/publications/renewable-energy-planning-database-monthly-extract,
  Open Government Licence v3.0. Projects over 150 kW (1 MW before 2021) with status
  "Operational" and an operational date; Northern Ireland excluded. Rooftop and other small
  solar is not in REPD (NESO's embedded solar capacity, above, covers it nationally).

Run: uv run python scripts/fetch_zones.py
"""

import io
import json
import urllib.request
from pathlib import Path

import pandas as pd

OUT = Path(__file__).parents[1] / "data/zones"
NESO = "https://api.neso.energy/api/3/action/package_show?id=historic-demand-data"
REPD = "https://assets.publishing.service.gov.uk/media/6a6cbdc00c36759b5ccaa305/REPD_Publication_Q2_2026.csv"
FIRST_YEAR = 2019
KEEP = {
    "ND": "national_demand_mw",
    "ENGLAND_WALES_DEMAND": "england_wales_demand_mw",
    "SCOTTISH_TRANSFER": "scottish_transfer_mw",
    "EMBEDDED_WIND_GENERATION": "embedded_wind_mw",
    "EMBEDDED_WIND_CAPACITY": "embedded_wind_capacity_mw",
    "EMBEDDED_SOLAR_GENERATION": "embedded_solar_mw",
    "EMBEDDED_SOLAR_CAPACITY": "embedded_solar_capacity_mw",
}
TECHNOLOGIES = {
    "Battery": "battery",
    "Solar Photovoltaics": "solar",
    "Wind Onshore": "onshore_wind",
    "Wind Offshore": "offshore_wind",
}


def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "OpenEnergy", "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return bytes(response.read())


def demand() -> pd.DataFrame:
    frames = []
    for resource in json.loads(get(NESO))["result"]["resources"]:
        year = resource["name"].removeprefix("Historic Demand Data ").strip()
        if not (year.isdigit() and int(year) >= FIRST_YEAR and resource["url"].endswith(".csv")):
            continue
        frame = pd.read_csv(io.BytesIO(get(resource["url"])))
        frame.columns = [c.upper() for c in frame.columns]
        text = frame["SETTLEMENT_DATE"].astype(str)
        # Newer files use ISO dates, older ones "01-JAN-2019"; never read ISO day-first.
        day = pd.to_datetime(text, format="ISO8601", errors="coerce")
        day = day.fillna(pd.to_datetime(text, format="mixed", dayfirst=True, errors="coerce"))
        local = day.dt.tz_localize("Europe/London", ambiguous="NaT", nonexistent="shift_forward")
        # Settlement periods count half-hours from UK local midnight, including clock changes.
        start = local.dt.normalize().dt.tz_convert("UTC") + pd.to_timedelta(
            30 * (frame["SETTLEMENT_PERIOD"] - 1), unit="min"
        )
        # Older files have no SCOTTISH_TRANSFER column: left blank there.
        out = frame.reindex(columns=list(KEEP)).rename(columns=KEEP)
        out.insert(0, "utc_timestamp", start)
        frames.append(out)
    table = (
        pd.concat(frames)
        .dropna(subset=["utc_timestamp"])
        .drop_duplicates("utc_timestamp")
        .sort_values("utc_timestamp")
    )
    table.insert(
        3, "scotland_demand_mw", table["national_demand_mw"] - table["england_wales_demand_mw"]
    )
    table["utc_timestamp"] = table["utc_timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return table


def capacity() -> pd.DataFrame:
    repd = pd.read_csv(io.BytesIO(get(REPD)), encoding="latin-1", low_memory=False)
    repd = repd[
        (repd["Development Status (short)"] == "Operational")
        & (repd["Country"] != "Northern Ireland")
    ]
    repd = repd[repd["Technology Type"].isin(list(TECHNOLOGIES))]
    when = pd.to_datetime(repd["Operational"], dayfirst=True, errors="coerce")
    mw = pd.to_numeric(repd["Installed Capacity (MWelec)"], errors="coerce")
    frame = pd.DataFrame(
        {
            "year": when.dt.year,
            "technology": repd["Technology Type"].map(TECHNOLOGIES),
            "zone": repd["Country"].map(
                lambda c: "scotland" if c == "Scotland" else "england_wales"
            ),
            "mw": mw,
        }
    ).dropna()
    added = frame.groupby(["technology", "zone", "year"])["mw"].sum()
    years = range(int(frame["year"].min()), 2027)
    rows = []
    for (tech, zone), series in added.groupby(level=["technology", "zone"]):
        total = series.droplevel(["technology", "zone"]).reindex(years, fill_value=0).cumsum()
        rows.extend(
            {"year": y, "technology": tech, "zone": zone, "mw": round(v, 1)}
            for y, v in total.items()
        )
    out = pd.DataFrame(rows)
    return out[out["year"] >= 2010].sort_values(["technology", "zone", "year"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    table = demand()
    table.to_csv(OUT / "demand_by_zone.csv", index=False)
    first, last = table["utc_timestamp"].iloc[0], table["utc_timestamp"].iloc[-1]
    print(f"demand_by_zone.csv: {len(table)} half-hours, {first} to {last}")
    caps = capacity()
    caps.to_csv(OUT / "capacity_by_year.csv", index=False)
    print(f"capacity_by_year.csv: {len(caps)} rows")


if __name__ == "__main__":
    main()
