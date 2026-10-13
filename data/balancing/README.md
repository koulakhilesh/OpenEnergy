# GB system (imbalance) prices

Written by `scripts/fetch_system_prices.py --end 2026-10-12` on 2026-10-13. Used by
`examples/imbalance_value.py`. OpenEnergy is not affiliated with or endorsed by Elexon.

## `gb_system_prices.csv`

The GB imbalance price for every half-hour settlement period from 2016-01-01 00:00 to
2026-10-12 23:30 UTC (189,024 rows). Columns: `utc_timestamp` (start of the period, UTC)
and `system_price_gbp_per_mwh`.

Source: Elexon, BMRS Insights API, settlement system prices (dataset DISEBSP),
<https://bmrs.elexon.co.uk/>, API
`https://data.elexon.co.uk/bmrs/api/v1/balancing/settlement/system-prices/{date}`.
Reused under the BMRS data licence,
<https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/>.

> Contains BMRS data © Elexon Limited copyright and database right 2026.

Changes: GB has had a single imbalance price since November 2015, so the system sell price
and system buy price are equal in every period (the script checks this) and one column is
kept; the API's other fields are dropped; prices are unchanged.

Known issues: 22 periods the API did not return are left blank (the last two belong to the
UK settlement day of 13 October 2026, not yet published). 4,951 periods are negative
(down to −£185.33/MWh on 2023-07-17) and the highest is £4,037.80/MWh (2021-09-09). Elexon
can revise system prices in later settlement runs; the file holds what the API returned on
2026-10-13.

Annual mean and standard deviation, £/MWh:

| Year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Mean | 39.4 | 44.3 | 57.3 | 42.0 | 35.1 | 113.3 | 200.1 | 94.5 | 71.2 | 80.6 | 104.1 |
| Std | 46.6 | 31.1 | 30.2 | 22.7 | 36.5 | 149.5 | 148.6 | 63.1 | 41.7 | 77.1 | 55.2 |

\* 1 January to 12 October.
