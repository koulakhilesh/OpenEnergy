"""How well do price-taking interconnector links reproduce GB prices and flows?

Each year is solved four ways on one GB bus: imports held at their historic output
(``fixed``); the ten built links trading at the neighbouring markets' actual day-ahead
prices at full capacity (``full``); the same links at the availability fitted from their
flows (``links``, the default since v4.2); and that with unit commitment (``uc``, marginal
price). Prices are compared with GB's actual day-ahead
prices, and link flows with the actual flows in Elexon's FUELHH data. Links need Irish
prices, so years start in 2019. The availability is fitted on flows from 2019 to 2025
(``scripts/fit_interconnector_availability.py``), so these years are in sample for flows;
prices are never fitted.

Sources: NESO historic generation mix and Interconnector Register (NESO Open Data Licence
v1.0); Ember European Wholesale Electricity Price Data (CC BY 4.0); ECB GBP rates; OPSD
time series; Elexon BMRS FUELHH. Contains BMRS data © Elexon Limited copyright and
database right 2026.

Run: uv run python examples/interconnector_check.py [2019 ... 2025] [--hurdle 5]
"""

import argparse
from pathlib import Path

import pandas as pd

from openenergy.data.ember import gb_prices
from openenergy.data.interconnectors import interconnector_flows
from openenergy.system.scenario import SystemScenario, run_system_scenario
from openenergy.system.validate import _daily_spread

DATA = Path(__file__).parents[1] / "data"
PRICES = [
    DATA / "time_series/time_series_60min_singleindex_filtered.csv",
    DATA / "prices/gb_day_ahead_ember.csv",
]
RUNS: dict[str, tuple[dict[str, object], dict[str, object]]] = {
    "fixed": ({"mode": "fixed"}, {}),
    "full": ({"mode": "links", "availability": 1.0}, {}),
    "links": ({"mode": "links"}, {}),
    "uc": ({"mode": "links"}, {"commitment": True}),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("years", nargs="*", type=int, default=list(range(2019, 2026)))
    parser.add_argument("--hurdle", type=float, default=0.0)
    args = parser.parse_args()
    flows = interconnector_flows(DATA / "system")
    rows = []
    for year in args.years:
        actual = gb_prices(
            PRICES, pd.Timestamp(year, 1, 1).date(), pd.Timestamp(year, 12, 31).date()
        )
        price = actual[0].prices
        days = flows.loc[str(year)]
        row = {
            "year": year,
            "actual_mean": price.mean(),
            "actual_spread": _daily_spread(price),
            "actual_imports_twh": days.filter(like="_import_mwh").sum().sum() / 1e6,
            "actual_exports_twh": days.filter(like="_export_mwh").sum().sum() / 1e6,
        }
        for label, (links, extra) in RUNS.items():
            system = {
                "data": str(DATA / "system"),
                "year": year,
                "interconnectors": {**links, "hurdle_gbp_per_mwh": args.hurdle},
                **extra,
            }
            s = run_system_scenario(
                SystemScenario.model_validate({"name": "check", "system": system})
            ).summary
            row[f"{label}_mean"] = s.price_mean
            row[f"{label}_spread"] = s.daily_spread
            if label != "fixed":
                row[f"{label}_imports_twh"] = s.imports_twh
                row[f"{label}_exports_twh"] = s.exports_twh
        rows.append(row)
        print(f"{year} done", flush=True)
    table = pd.DataFrame(rows).set_index("year")
    print(f"\nhurdle {args.hurdle} GBP/MWh")
    for group in ("mean", "spread", "imports_twh", "exports_twh"):
        print(f"\n{group}")
        print(table.filter(like=group).round(1).to_string())


if __name__ == "__main__":
    main()
