# Supply tightness

How tight GB's supply was each half-hour, written by `scripts/fetch_scarcity.py`, and the
evening-premium study built from it by `scripts/evening_premium.py`.
OpenEnergy is not affiliated with or endorsed by Elexon or NESO.

Source: Elexon, BMRS Insights API (<https://bmrs.elexon.co.uk/>), dataset `LOLPDRM`
(loss-of-load probability and de-rated margin, calculated by NESO). Licence:
[BMRS data licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/).
Contains BMRS data © Elexon Limited copyright and database right 2026.

## `lolp.csv`

One row per half-hour from 1 July 2018 to 29 October 2026 (Elexon has none before 2018):

| Column | Meaning |
|---|---|
| `utc_timestamp` | Start of the half-hour (UTC) |
| `lolp` | Loss-of-load probability, 0 to 1 |
| `derated_margin_mw` | Spare capacity after de-rating for expected plant failures (MW) |
| `published` | When that value was issued |

Changes: of the values published for each half-hour (up to about 12 hours ahead), only the
last one issued before it started is kept, the one cash-out uses for the reserve scarcity
price. It is close to outturn, not a day-ahead forecast. Half-hours with no value are left
out.

## `evening_premium_by_*.csv`

OpenEnergy model output. The merit-order backcast's hourly gap (actual day-ahead price
minus modelled price, July 2018 to 2025) against the hourly mean of the values above: by
de-rated margin band, by UTC hour and by year, with LoLP × £6,000/MWh (the value of lost
load in cash-out) as the market's own scarcity price. Day-ahead prices keep their own
credits (OPSD and Ember, `data/prices`).
