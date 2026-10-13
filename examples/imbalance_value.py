"""Is GB balancing (the imbalance price) worth chasing with open data?

Each UTC day a 1 MW / 2 MWh battery takes a day-ahead position planned at noon the day
before on last week's prices, settled at the day-ahead price (Ember). In delivery it may
deviate from that position half-hour by half-hour; deviations are settled at the GB system
(imbalance) price (Elexon). Compared on the same days, after a GBP 5/MWh wear cost:

- follow day-ahead:  deliver the day-ahead position exactly
- perfect:           deviations planned knowing the day's system prices (an upper bound)
- re-plan, t-2:      before each half-hour, re-plan the rest of the day on the latest
                     published system price (two periods back) for the next hour and the
                     day-ahead price after that; only the next half-hour is kept
- re-plan, known DA: once the day-ahead auction has cleared, re-plan on its prices and
                     settle the difference at the system price (the value of knowing the
                     day-ahead price, not of balancing)
- imbalance only:    no day-ahead position; re-plan on the t-2 system price, then
                     yesterday's prices for the rest of the day

Sources: Ember European Wholesale Electricity Price Data (CC BY 4.0); ECB GBP rates;
Elexon BMRS system prices. Contains BMRS data © Elexon Limited copyright and database
right 2026.

Run: uv run python examples/imbalance_value.py [2019 2022 2024 2025]  (about 3 min a year)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from openenergy.assets import BatterySpec
from openenergy.assets.battery import BatteryState
from openenergy.data import EmberPriceSource
from openenergy.dispatch import DispatchConfig, optimise_dispatch

DATA = Path(__file__).parents[1] / "data"
WEAR = 5.0
SPEC = BatterySpec(power_mw=1, energy_mwh=2, eta_charge=0.95, eta_discharge=0.95)
DAY = pd.Timedelta(days=1)
HALF = 0.5
CASES = ["follow day-ahead", "perfect", "re-plan, t-2", "re-plan, known DA", "imbalance only"]


def plan(
    prices: np.ndarray, energy: float, target: float, step: float
) -> tuple[np.ndarray, np.ndarray]:
    usable = SPEC.energy_mwh
    state = BatteryState(energy_mwh=min(max(energy, 0.0), usable))
    config = DispatchConfig(degradation_cost=WEAR, end_soc=min(max(target / usable, 0.0), 1.0))
    result = optimise_dispatch(SPEC, state, prices, step, config)
    return result.charge_mw, result.discharge_mw


def rolling(forecasts: list[np.ndarray], start: float) -> tuple[np.ndarray, np.ndarray]:
    """Keep the first half-hour of a fresh plan made before each half-hour."""
    charge, discharge = np.zeros(48), np.zeros(48)
    energy = start
    for t, forecast in enumerate(forecasts):
        left = HALF * (48 - t)
        # Head back towards the starting energy, as far as the remaining time allows.
        target = min(
            max(start, energy - left / SPEC.eta_discharge), energy + left * SPEC.eta_charge
        )
        c, d = plan(forecast, energy, target, HALF)
        charge[t], discharge[t] = c[0], d[0]
        energy += (c[0] * SPEC.eta_charge - d[0] / SPEC.eta_discharge) * HALF
    return charge, discharge


def main(years: list[int]) -> None:
    day_ahead = EmberPriceSource(DATA / "prices/gb_day_ahead_ember.csv").prices().prices
    system = pd.read_csv(DATA / "balancing/gb_system_prices.csv")
    system.index = pd.to_datetime(system.pop("utc_timestamp"), utc=True)
    imbalance = system["system_price_gbp_per_mwh"]

    print(f"{'year':<6}{'days':>5}  {'case':<20}{'revenue':>10}{'vs day-ahead':>14}")
    for year in years:
        totals = dict.fromkeys(CASES, 0.0)
        energy = dict.fromkeys(CASES, SPEC.energy_mwh / 2)
        days = 0
        for start in pd.date_range(f"{year}-01-01", f"{year}-12-31", tz="UTC"):
            hours = pd.date_range(start, periods=24, freq="h")
            halves = pd.date_range(start, periods=48, freq="30min")
            actual = day_ahead.reindex(hours).to_numpy()
            last_week = day_ahead.reindex(hours - 7 * DAY).to_numpy()
            imb = imbalance.reindex(halves).to_numpy()
            yesterday = imbalance.reindex(halves - DAY).to_numpy()
            if np.isnan(np.concatenate([actual, last_week, imb, yesterday])).any():
                continue
            days += 1
            da_half = np.repeat(actual, 2)
            lagged = np.concatenate([yesterday[-2:], imb[:-2]])
            for case in CASES:
                start_energy = energy[case]
                position = np.zeros(48)
                if case != "imbalance only":
                    c, d = plan(last_week, start_energy, start_energy, 1.0)
                    position = np.repeat(d - c, 2)
                if case == "follow day-ahead":
                    charge, discharge = np.repeat(c, 2), np.repeat(d, 2)
                elif case == "perfect":
                    charge, discharge = plan(imb, start_energy, start_energy, HALF)
                elif case == "re-plan, known DA":
                    charge, discharge = plan(da_half, start_energy, start_energy, HALF)
                else:
                    base = yesterday if case == "imbalance only" else da_half
                    forecasts = []
                    for t in range(48):
                        forecast = base[t:].copy()
                        forecast[:2] = lagged[t]
                        forecasts.append(forecast)
                    charge, discharge = rolling(forecasts, start_energy)
                net = discharge - charge
                money = HALF * (da_half @ position + imb @ (net - position))
                totals[case] += money - WEAR * HALF * float((charge + discharge).sum())
                energy[case] = start_energy + HALF * float(
                    (charge * SPEC.eta_charge - discharge / SPEC.eta_discharge).sum()
                )
        base = totals["follow day-ahead"]
        for case in CASES:
            change = totals[case] / base - 1 if base else float("nan")
            print(f"{year:<6}{days:>5}  {case:<20}{totals[case]:>10,.0f}{change:>14.1%}")


if __name__ == "__main__":
    main([int(arg) for arg in sys.argv[1:]] or [2019, 2022, 2024, 2025])
