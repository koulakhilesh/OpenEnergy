"""Download the public data behind OpenEnergy's GB system model into data/system/.

Sources (all reused under their licences; OpenEnergy is not affiliated with or endorsed by
any of them):

- NESO, Historic generation mix and carbon intensity,
  https://www.neso.energy/data-portal/historic-generation-mix. NESO Open Data Licence v1.0.
  Supported by National Energy SO Open Data.
- DESNZ, DUKES 2026 tables 5.8 (plant capacity by region) and 5.10 (thermal efficiency),
  https://www.gov.uk/government/statistics/electricity-chapter-5-digest-of-united-kingdom-energy-statistics-dukes.
  Open Government Licence v3.0.
- DESNZ, Quarterly Energy Prices table 3.2.1 (fuels bought by major power producers),
  https://www.gov.uk/government/statistical-data-sets/prices-of-fuels-purchased-by-major-power-producers.
  Open Government Licence v3.0.
- World Bank, Carbon Pricing Dashboard, EU ETS price on 1 April (US$/tCO2e),
  https://carbonpricingdashboard.worldbank.org/compliance/price. CC BY 4.0.
- European Central Bank, euro reference exchange rates (GBP, USD), https://data.ecb.europa.eu/.
- HMRC, Excise Notice CCL1/6, carbon price support rates,
  https://www.gov.uk/government/publications/excise-notice-ccl16-a-guide-to-carbon-price-floor.
  Open Government Licence v3.0.

Run: uv run --with openpyxl python scripts/fetch_system_data.py
"""

import csv
import io
import time
import urllib.request
from pathlib import Path

import pandas as pd

OUTPUT = Path(__file__).parents[1] / "data/system"
START, END = "2015-01-01", "2020-10-01"
YEARS = range(2014, 2021)

NESO_MIX = (
    "https://api.neso.energy/dataset/88313ae5-94e4-4ddc-a790-593554d8c6b9/resource/"
    "f93d1835-75bc-43e5-84ad-12472b180a98/download/df_fuel_ckan.csv"
)
MIX_COLUMNS = [
    "GAS", "COAL", "NUCLEAR", "WIND", "WIND_EMB", "HYDRO", "IMPORTS", "BIOMASS", "OTHER",
    "SOLAR", "STORAGE", "GENERATION",
]  # fmt: skip
DUKES_5_8 = "https://assets.publishing.service.gov.uk/media/6a6a3631862aaf18d9c629ec/DUKES_5.8.xlsx"
DUKES_5_10 = (
    "https://assets.publishing.service.gov.uk/media/6a6a364b0ddb7e4831c629f2/DUKES_5.10.xlsx"
)
QEP_3_2_1 = "https://assets.publishing.service.gov.uk/media/6ab54240734e2435f202f060/table_321.xlsx"
ECB = (
    "https://data-api.ecb.europa.eu/service/data/EXR/D.GBP+USD.EUR.SP00.A"
    "?startPeriod={year}-03-20&endPeriod={year}-04-01&format=csvdata"
)
GB_REGIONS = ("England and Wales", "Scotland")

# World Bank Carbon Pricing Dashboard, EU ETS, US$/tCO2e on 1 April (accessed 2026-10-10).
# The dashboard blocks scripted downloads, so the published values are recorded here.
EU_ETS_USD = {
    2015: 7.689825, 2016: 5.921776, 2017: 5.644848, 2018: 16.26372, 2019: 24.505716,
    2020: 18.53652,
}  # fmt: skip
# HMRC carbon price support rates: gas GBP/kWh, coal GBP/GJ (gross calorific value).
CPS = {2015: (0.00334, 1.56860), **dict.fromkeys(range(2016, 2021), (0.00331, 1.54790))}


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "openenergy-fetch"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return bytes(response.read())
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def generation_mix() -> None:
    frame = pd.read_csv(io.BytesIO(download(NESO_MIX)), usecols=["DATETIME", *MIX_COLUMNS])
    stamps = pd.to_datetime(frame["DATETIME"])
    frame = frame[(stamps >= START) & (stamps < END)]
    expected = (pd.Timestamp(END) - pd.Timestamp(START)) // pd.Timedelta(minutes=30)
    if len(frame) != expected:
        raise ValueError(f"expected {expected} half-hours from NESO, got {len(frame)}; retry")
    out = frame[MIX_COLUMNS].rename(columns=str.lower)
    if (out % 1 != 0).any().any():
        raise ValueError("NESO generation mix has fractional MW; update the integer conversion")
    out = out.astype(int)
    out.insert(0, "utc_timestamp", stamps[frame.index].dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
    out.to_csv(OUTPUT / "generation_mix.csv", index=False)
    print(f"generation_mix.csv: {len(out)} half-hours")


def _table(sheet: pd.DataFrame, title: str, labels: int) -> pd.DataFrame:
    """The table titled ``title``: ``labels`` label columns, then one column per year."""
    header = sheet.index[sheet[0].astype(str).str.startswith(title)][0] + 1
    end = header + 1
    while end < len(sheet) and not str(sheet.iat[end, 0]).startswith("Table"):
        end += 1
    body = sheet.iloc[header + 1 : end]
    names = body.iloc[:, :labels].map(lambda v: str(v).split("[")[0].strip())
    values = body.iloc[:, labels:].apply(pd.to_numeric, errors="coerce")
    values.columns = [int(float(str(v).split("[")[0])) for v in sheet.iloc[header, labels:]]
    values.index = pd.MultiIndex.from_frame(names) if labels > 1 else names.iloc[:, 0]
    return values


def fleet() -> None:
    capacity = pd.read_excel(io.BytesIO(download(DUKES_5_8)), sheet_name="5.8", header=None)
    by_fuel = _table(capacity, "Table 5.8.A", labels=2)
    by_tech = _table(capacity, "Table 5.8.C", labels=2)
    efficiency = pd.read_excel(
        io.BytesIO(download(DUKES_5_10)), sheet_name="5.10.B and 5.10.C", header=None
    )
    eff = _table(efficiency, "Table 5.10.C", labels=1)

    def gb(table: pd.DataFrame, item: str) -> pd.Series:
        return sum(table.loc[(region, item)] for region in GB_REGIONS)

    columns = {
        "ccgt_mw": gb(by_tech, "CCGT stations"),
        "coal_mw": gb(by_fuel, "Coal fired"),
        "gas_turbine_mw": gb(by_tech, "Gas turbines"),
        "oil_engine_mw": gb(by_tech, "Oil engines"),
        "nuclear_mw": gb(by_fuel, "Nuclear stations"),
        "pumped_storage_mw": gb(by_fuel, "Pumped storage hydro"),
        "ccgt_efficiency": eff.loc["Combined cycle gas turbine stations"] / 100,
        "coal_efficiency": eff.loc["Coal fired stations"] / 100,
    }
    out = pd.DataFrame(columns).loc[list(YEARS)].round(4)
    out.index.name = "year"
    out.to_csv(OUTPUT / "fleet.csv")
    print(f"fleet.csv: {len(out)} years")


def fuel_prices() -> None:
    sheet = pd.read_excel(io.BytesIO(download(QEP_3_2_1)), sheet_name="3.2.1", header=None)
    header = sheet.index[sheet[0].astype(str) == "Year"][0]
    body = sheet.iloc[header + 1 :, :7].dropna(subset=[1])
    body = body[body[1].astype(str).str.contains(" to ")]
    body = body[pd.to_numeric(body[0], errors="coerce").isin(YEARS)]
    quarters = {"Jan to Mar": 1, "Apr to Jun": 2, "Jul to Sep": 3, "Oct to Dec": 4}
    out = pd.DataFrame(
        {
            "year": body[0].astype(int),
            "quarter": body[1].str.strip().map(quarters).astype(int),
            "coal_p_per_kwh": body[3].astype(float),
            "oil_p_per_kwh": body[5].astype(float),
            "gas_p_per_kwh": body[6].astype(float),
        }
    ).round(4)
    out.to_csv(OUTPUT / "fuel_prices.csv", index=False)
    print(f"fuel_prices.csv: {len(out)} quarters")


def carbon_prices() -> None:
    rows = []
    for year, usd in EU_ETS_USD.items():
        text = download(ECB.format(year=year)).decode()
        rates: dict[str, tuple[str, float]] = {}
        for record in csv.DictReader(io.StringIO(text)):
            currency, day = record["CURRENCY"], record["TIME_PERIOD"]
            if currency not in rates or day > rates[currency][0]:
                rates[currency] = (day, float(record["OBS_VALUE"]))
        if rates["GBP"][0] != rates["USD"][0]:
            raise ValueError(f"ECB rates for {year} are on different days: {rates}")
        gas, coal = CPS[year]
        day = rates["GBP"][0]
        rows.append([f"{year}-04-01", usd, day, rates["USD"][1], rates["GBP"][1], gas, coal])
    header = [
        "valid_from", "eu_ets_usd_per_t", "fx_date", "usd_per_eur", "gbp_per_eur",
        "cps_gas_gbp_per_kwh", "cps_coal_gbp_per_gj",
    ]  # fmt: skip
    with (OUTPUT / "carbon_prices.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"carbon_prices.csv: {len(rows)} years")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    generation_mix()
    fleet()
    fuel_prices()
    carbon_prices()


if __name__ == "__main__":
    main()
