"""Fetch the inputs for the battery investment case into data/invest/.

- NESO Capacity Market register (NESO Open Data Licence v1.0): every auction's clearing
  price and the de-rating factors for storage by duration.
- NREL Annual Technology Baseline 2024 (CC BY 4.0): utility-scale battery capital cost and
  fixed O&M by duration and year, Moderate scenario, market case, in 2022 US dollars.
- ECB euro reference rates: the 2022 average pounds per US dollar, to convert ATB's costs.

Run: uv run python scripts/fetch_invest.py
"""

import io
import json
import urllib.request
from pathlib import Path

import pandas as pd

OUT = Path(__file__).parents[1] / "data/invest"
NESO = "https://api.neso.energy/api/3/action/package_show?id=capacity-market-register"
ATB = "https://oedi-data-lake.s3.amazonaws.com/ATB/electricity/parquet/2024/v3.0.0/ATBe.parquet"
ECB = "https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A?startPeriod=2022-01-01&endPeriod=2022-12-31&format=csvdata"


def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "OpenEnergy"})
    with urllib.request.urlopen(request, timeout=300) as response:
        body: bytes = response.read()
        return body


def neso(resources: list[dict], name: str) -> pd.DataFrame:
    url = next(r["url"] for r in resources if r["name"] == name)
    return pd.read_csv(io.BytesIO(get(url)))


def capacity_market() -> None:
    resources = json.loads(get(NESO))["result"]["resources"]
    auctions = neso(resources, "Capacity Market Auction Static Data")
    auctions = pd.DataFrame(
        {
            "auction": auctions["Auction Name"],
            "clearing_gbp_per_kw_year": auctions["Clearing Price_GBP per kW per year"],
        }
    ).dropna()
    auctions["delivery_year"] = auctions["auction"].str[:4].astype(int)
    auctions["type"] = auctions["auction"].str.extract(r"\((T-\d|TR)\)", expand=False)
    auctions.to_csv(OUT / "capacity_market_auctions.csv", index=False)
    factors = neso(resources, "Capacity Market De-Rating Factors")
    storage = factors[factors["Primary Fuel Type"] == "Storage"].copy()
    hours = storage["Generating Technology Class"].str.extract(r"Duration ([\d.]+)h", expand=False)
    storage = pd.DataFrame(
        {
            "auction": storage["Auction Name"],
            "duration_hours": hours.astype(float),
            "derating_factor": storage["De Rating Factor"],
        }
    ).dropna()
    storage.sort_values(["auction", "duration_hours"]).to_csv(
        OUT / "capacity_market_storage_derating.csv", index=False
    )


def battery_costs() -> None:
    atb = pd.read_parquet(io.BytesIO(get(ATB)))
    rows = atb[
        (atb["technology"] == "Utility-Scale Battery Storage")
        & (atb["scenario"] == "Moderate")
        & (atb["core_metric_case"] == "Market")
        & (atb["crpyears"].astype(str) == "20")
        & atb["core_metric_parameter"].isin(["CAPEX", "Fixed O&M"])
    ]
    table = rows.pivot_table(
        index=["techdetail", "core_metric_variable"],
        columns="core_metric_parameter",
        values="value",
    ).reset_index()
    table = pd.DataFrame(
        {
            "duration_hours": table["techdetail"].str.extract(r"(\d+)Hr", expand=False).astype(int),
            "year": table["core_metric_variable"].astype(int),
            "capex_usd2022_per_kw": table["CAPEX"].round(1),
            "fixed_om_usd2022_per_kw_year": table["Fixed O&M"].round(2),
        }
    )
    rates = {}
    for currency in ("GBP", "USD"):
        frame = pd.read_csv(io.BytesIO(get(ECB.format(currency=currency))))
        rates[currency] = frame["OBS_VALUE"].astype(float).mean()
    table["gbp_per_usd_2022"] = round(rates["GBP"] / rates["USD"], 4)
    table.sort_values(["duration_hours", "year"]).to_csv(OUT / "battery_costs.csv", index=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    capacity_market()
    battery_costs()
    for path in sorted(OUT.glob("*.csv")):
        print(path.name, len(pd.read_csv(path)), "rows")


if __name__ == "__main__":
    main()
