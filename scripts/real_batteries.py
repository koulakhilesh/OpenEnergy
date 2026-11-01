"""Compare GB's real grid batteries with OpenEnergy's optimiser, year by year.

Reads data/fleet/ (scripts/fetch_fleet.py) and writes:

- data/fleet/real_vs_model.csv: by year, the real fleet's metered energy valued at the
  day-ahead price, its contracted position (PN) at the day-ahead price, Balancing
  Mechanism cashflow, imbalance at the system price and their estimated total, per MW-year
  of registered capacity, with REPD's battery capacity for coverage, and what OpenEnergy's
  optimiser earns per MW-year at the day-ahead price for a
  1-hour and a 2-hour battery (95% each way, £5/MWh wear) planning on perfect foresight,
  OpenEnergy's forecast and last week's prices (revenue before wear, as the backtest
  reports it);
- data/fleet/real_by_zone.csv: the real fleet's figures by year and zone;
- data/fleet/hour_profile.csv: by year and UTC hour of day, the real fleet's mean metered
  net output per MW of capacity running, and the 2-hour perfect-foresight plan's.

Run: uv run python scripts/real_batteries.py
"""

from datetime import date
from pathlib import Path

import pandas as pd

from openenergy.assets import BatterySpec
from openenergy.backtest import BacktestConfig, run_backtest
from openenergy.data.batteries import RealBatteries
from openenergy.data.ember import gb_prices
from openenergy.dispatch import DispatchConfig
from openenergy.forecast import NaiveLastWeek, PerfectForesight, PrecomputedForecast

ROOT = Path(__file__).parents[1]
FLEET = ROOT / "data/fleet"
PRICES = ROOT / "data/prices/gb_day_ahead_ember.csv"
FORECAST = ROOT / "data/forecasts/gb_fundamentals_day_ahead.csv"
YEARS = range(2021, 2026)


def model_year(year: int) -> tuple[dict[str, float], pd.Series]:
    window = gb_prices([PRICES], date(year - 1, 12, 1), date(year, 12, 31))[0]
    days = pd.date_range(date(year, 1, 1), date(year, 12, 31)).date.tolist()
    config = BacktestConfig(dispatch=DispatchConfig(degradation_cost=5))
    out: dict[str, float] = {}
    profile = pd.Series(dtype=float)
    for hours in (1, 2):
        battery = BatterySpec(power_mw=1, energy_mwh=hours, eta_charge=0.95, eta_discharge=0.95)
        forecasters = {
            "perfect": PerfectForesight(window),
            "fundamentals": PrecomputedForecast(FORECAST, name="fundamentals"),
            "naive": NaiveLastWeek(),
        }
        for name, forecaster in forecasters.items():
            run = run_backtest(battery, window, forecaster, config, days)
            out[f"model_{hours}h_{name}_per_mw_year"] = float(run.daily["revenue"].sum())
            if hours == 2 and name == "perfect":
                net = run.intervals["discharge_mw"] - run.intervals["charge_mw"]
                profile = net.groupby(pd.DatetimeIndex(net.index).hour).mean()
    return out, profile


def main() -> None:
    real = RealBatteries(FLEET)
    years = real.by_year()
    capacity_table = pd.read_csv(ROOT / "data/zones/capacity_by_year.csv")
    repd = capacity_table[capacity_table["technology"] == "battery"].groupby("year")["mw"].sum()
    zones = real.by_year(by_zone=True)
    zone_columns = ["units", "mw_years", "discharge_hours", "round_trip"] + [
        c for c in zones if c.endswith("_per_mw_year")
    ]
    zones[zone_columns].round(3).to_csv(FLEET / "real_by_zone.csv")
    hourly = real.hourly()
    capacity = real.units()["generation_capacity_mw"]
    daily = real.daily().reset_index()
    running = daily.assign(mw=daily["unit"].map(capacity)).groupby("date")["mw"].sum()

    rows, profiles = [], []
    for year in YEARS:
        if year not in years.index:
            continue
        model, plan = model_year(year)
        row = years.loc[year]
        rows.append(
            {
                "year": year,
                "units": int(row["units"]),
                "mw_years": round(row["mw_years"], 1),
                "repd_battery_mw": round(float(repd.get(year, float("nan"))), 0),
                "discharge_hours": round(row["discharge_hours"], 0),
                "round_trip": round(row["round_trip"], 3),
                "real_metered_day_ahead_per_mw_year": round(
                    row["metered_value_day_ahead_per_mw_year"], 0
                ),
                "real_pn_day_ahead_per_mw_year": round(row["pn_value_day_ahead_per_mw_year"], 0),
                "real_bm_net_per_mw_year": round(row["bm_net_per_mw_year"], 0),
                "real_imbalance_per_mw_year": round(row["imbalance_per_mw_year"], 0),
                "real_estimated_total_per_mw_year": round(row["estimated_total_per_mw_year"], 0),
                **{k: round(v, 0) for k, v in model.items()},
            }
        )
        fleet = hourly.loc[str(year), "metered_net_mw"]
        mw_running = running.reindex(fleet.index.normalize().tz_localize(None)).to_numpy()
        per_mw = fleet / mw_running
        real_profile = per_mw.groupby(per_mw.index.hour).mean()
        profiles.append(
            pd.DataFrame(
                {
                    "year": year,
                    "hour": range(24),
                    "real_net_per_mw": real_profile.round(3).to_numpy(),
                    "model_2h_perfect_net_mw": plan.round(3).to_numpy(),
                }
            )
        )
        print(rows[-1])
    pd.DataFrame(rows).to_csv(FLEET / "real_vs_model.csv", index=False)
    pd.concat(profiles).to_csv(FLEET / "hour_profile.csv", index=False)


if __name__ == "__main__":
    main()
