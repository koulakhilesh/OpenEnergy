"""Download GB hourly day-ahead prices (Ember) and ECB daily GBP rates into data/prices/.

Sources (reused under their licences; OpenEnergy is not affiliated with or endorsed by
either):

- Ember, European Wholesale Electricity Price Data, hourly, United Kingdom file,
  https://ember-energy.org/data/european-wholesale-electricity-price-data/. CC BY 4.0.
  Ember's primary sources for the UK are ENTSO-E and EMR Settlement.
- European Central Bank, euro foreign exchange reference rates, series EXR.D.GBP.EUR.SP00.A,
  https://data.ecb.europa.eu/.

Prices are stored in EUR/MWh exactly as published; OpenEnergy converts them to GBP with the
ECB rate for each day. `openenergy data update` does the same into a user cache.

Run: uv run python scripts/fetch_prices.py
"""

from pathlib import Path

from openenergy.data.update import update_prices

OUTPUT = Path(__file__).parents[1] / "data/prices"


def main() -> None:
    path, hours, first, last = update_prices(OUTPUT)
    print(f"{path.name}: {hours} hours, {first} to {last} UTC")


if __name__ == "__main__":
    main()
