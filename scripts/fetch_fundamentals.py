"""Download the daily gas price and the day-ahead demand and wind forecasts into data/fundamentals/.

These are what is known about tomorrow when a day-ahead plan is made: the gas price, and
the system operator's demand and wind forecasts. The system model uses the gas price; the
fundamentals price forecast uses all three.

Sources (reused under their licences; OpenEnergy is not affiliated with or endorsed by any
of them):

- Office for National Statistics, System Average Price (SAP) of gas, daily, from National
  Gas Transmission,
  https://www.ons.gov.uk/economy/economicoutputandproductivity/output/datasets/systemaveragepricesapofgas.
  Open Government Licence v3.0.
- NESO, Day Ahead Demand Forecast (historic day-ahead national demand forecasts),
  https://www.neso.energy/data-portal/1-day-ahead-demand-forecast. NESO Open Data Licence
  v1.0. Supported by National Energy SO Open Data.
- Elexon, BMRS Insights API, wind generation forecast (dataset WINDFOR), https://bmrs.elexon.co.uk/,
  reused under the BMRS data licence,
  https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/.
  Contains BMRS data © Elexon Limited copyright and database right 2026.

Run: uv run python scripts/fetch_fundamentals.py
"""

from datetime import date
from pathlib import Path

from openenergy.data.update import update_fundamentals

OUTPUT = Path(__file__).parents[1] / "data/fundamentals"
END = date(2026, 10, 30)


def main() -> None:
    for name, rows, first, last in update_fundamentals(OUTPUT, END):
        print(f"{name}: {rows} rows, {first} to {last}")


if __name__ == "__main__":
    main()
