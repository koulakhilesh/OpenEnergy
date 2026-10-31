"""Fetch the evidence on GB transmission constraints into data/constraints/.

Two NESO datasets (NESO Open Data Licence v1.0), written as:

- constraint_breakdown_daily.csv: the daily cost (GBP) and volume (MWh) of NESO's actions
  to manage thermal and voltage constraints, the largest loss and system inertia, from
  1 April 2021 (NESO's "Constraint Breakdown Costs and Volume", one file per financial
  year, concatenated with values unchanged);
- day_ahead_boundaries_monthly.csv: for each boundary group and month, the day-ahead limit
  and flow NESO published for each half-hour, summarised (NESO's "Day Ahead Constraint
  Flows and Limits", which keeps the latest three years and the current one): half-hours,
  mean limit and flow (MW), and the share of half-hours with flow at least 95% of the limit
  and above it. The raw file (about 30 MB) is not bundled.

Run: uv run python scripts/fetch_constraints.py
"""

import io
import json
import urllib.request
from pathlib import Path

import pandas as pd

OUT = Path(__file__).parents[1] / "data/constraints"
API = "https://api.neso.energy/api/3/action/package_show?id="
FIRST_FINANCIAL_YEAR = "2021-2022"


def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "OpenEnergy", "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return bytes(response.read())


def resources(dataset: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = json.loads(get(API + dataset))["result"]["resources"]
    return found


def breakdown() -> pd.DataFrame:
    frames = []
    for resource in resources("constraint-breakdown"):
        year = resource["name"].removeprefix("Constraint Breakdown ").strip()
        if not resource["url"].endswith(".csv") or year < FIRST_FINANCIAL_YEAR:
            continue
        frame = pd.read_csv(io.BytesIO(get(resource["url"])))
        frame["Date"] = pd.to_datetime(frame["Date"], format="mixed").dt.strftime("%Y-%m-%d")
        frames.append(frame)
    return pd.concat(frames).sort_values("Date").reset_index(drop=True)


def boundaries() -> pd.DataFrame:
    (resource,) = [
        r for r in resources("day-ahead-constraint-flows-and-limits") if r["url"].endswith(".csv")
    ]
    raw = pd.read_csv(io.BytesIO(get(resource["url"])))
    raw.columns = pd.Index(["group", "time", "limit_mw", "flow_mw"])
    raw = raw[raw["limit_mw"] > 0].dropna(subset=["flow_mw"])
    raw["month"] = pd.to_datetime(raw["time"], format="ISO8601").dt.strftime("%Y-%m")
    share = raw["flow_mw"] / raw["limit_mw"]
    raw["near_limit"] = share >= 0.95
    raw["above_limit"] = share > 1
    table = raw.groupby(["group", "month"], as_index=False).agg(
        half_hours=("flow_mw", "size"),
        limit_mw=("limit_mw", "mean"),
        flow_mw=("flow_mw", "mean"),
        near_limit=("near_limit", "mean"),
        above_limit=("above_limit", "mean"),
    )
    return table.round({"limit_mw": 0, "flow_mw": 0, "near_limit": 4, "above_limit": 4})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    costs = breakdown()
    costs.to_csv(OUT / "constraint_breakdown_daily.csv", index=False)
    print(f"constraint_breakdown_daily.csv: {len(costs)} days to {costs.Date.max()}")
    table = boundaries()
    table.to_csv(OUT / "day_ahead_boundaries_monthly.csv", index=False)
    print(f"day_ahead_boundaries_monthly.csv: {len(table)} rows to {table.month.max()}")


if __name__ == "__main__":
    main()
