# GB day-ahead prices after 2020

Written by `scripts/fetch_prices.py` (or `openenergy data update`, which writes the same two
files to a user cache). Downloaded on 2026-10-10. OpenEnergy is not affiliated with or
endorsed by Ember or the European Central Bank.

## `gb_day_ahead_ember.csv`

Hourly GB day-ahead electricity price, 2016-06-29 23:00 to 2026-10-05 22:00 UTC (90,000
rows, no gaps). Columns: `utc_timestamp` (start of the hour, UTC) and `price_eur_per_mwh`.

Source: Ember, *European Wholesale Electricity Price Data*, hourly file `United
Kingdom.csv`, <https://ember-energy.org/data/european-wholesale-electricity-price-data/>.
Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Ember names its
primary sources for the UK as the ENTSO-E Transparency Platform and EMR Settlement, and
interpolates missing values from nearby hours.

Changes: only the UTC timestamp and the price are kept; timestamps are written in ISO 8601
with a `Z` suffix; prices are unchanged (EUR/MWh).

Check: where it overlaps the OPSD file (July 2016 to September 2020, 37,239 hours), the
price converted to GBP matches OPSD's GB day-ahead price with correlation 0.99996 and a
mean absolute difference of £0.11/MWh; yearly means agree within £0.01.

Known issues: 615 hours are negative (down to −€60/MWh) and 38 are €1,000/MWh or more (up
to €2,576/MWh, in 2021–2022); both are kept. Before 2021 the series is the ENTSO-E GB price
(as in OPSD); from 2021 it follows EMR Settlement, whose own reuse terms could not be read
(the site blocks scripted access), so OpenEnergy relies on Ember's CC BY 4.0 publication.

## `ecb_gbp_per_eur.csv`

Daily euro reference rate for the pound, 2016-06-01 to 2026-10-09 (2,653 business days).
Columns: `date` and `gbp_per_eur`.

Source: European Central Bank, euro foreign exchange reference rates, series
EXR.D.GBP.EUR.SP00.A, <https://data.ecb.europa.eu/>. Stored unchanged.

OpenEnergy converts each hour's price at the rate for its UTC day, or the latest earlier
rate on weekends and holidays (source: ECB).
