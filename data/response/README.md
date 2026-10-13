# GB dynamic frequency response

Written by `scripts/fetch_response_data.py` on 2026-10-13 (with `--utilisation` for the
second file). OpenEnergy is not affiliated with or endorsed by NESO.

## `gb_dynamic_response.csv`

Day-ahead auction results for NESO's dynamic response services, one row per delivery
block (EFA block, normally four hours), 2021-09-15 22:00 to 2026-10-14 22:00 UTC (11,130
blocks, no gaps; the ten blocks on clock-change days are three or five hours long).
Columns: `utc_start`, `utc_end`, then for each service `<service>_gbp_per_mw_h` (clearing
price, GBP per MW per hour of availability) and `<service>_mw` (cleared volume).

| Service | Code | Responds when frequency | Energy held |
|---|---|---|---|
| Dynamic Containment low / high | `dcl` / `dch` | falls / rises past ±0.2 Hz, mostly | 15 minutes |
| Dynamic Moderation low / high | `dml` / `dmh` | moves past ±0.1 Hz | 30 minutes |
| Dynamic Regulation low / high | `drl` / `drh` | moves at all past ±0.015 Hz | 60 minutes |

Sources (National Energy System Operator, NESO Open Data Licence v1.0,
<https://www.neso.energy/data-portal/neso-open-licence>):

- *Dynamic Containment, Regulation and Moderation auction results*, "DC, DR & DM Results
  Summary Master Data 2021-2023",
  <https://www.neso.energy/data-portal/dynamic-containment-data>. Delivery times there are
  UK local time; they are converted to UTC.
- *Enduring Auction Capability (EAC) auction results*, response rows of the results
  summary files (FY2023, FY2024 and FY2025 archives and the current file),
  <https://www.neso.energy/data-portal/eac-auction-results>. Delivery times are UTC. EAC
  replaced the earlier auctions from 2 November 2023; where both list a block, EAC is kept.

Supported by National Energy SO Open Data.

Changes: response services only (reserve products on EAC are dropped); one row per block
with each service's price and volume side by side; times in UTC.

Known issues: DM and DR start on 2022-03-26 (blank before). A cleared volume of 0 with a
price of 0 means nothing was bought. Prices can be negative, mostly for the high services
(DM high 3,008 blocks, DR high 5,506), where providers pay to take part. Dynamic
Containment before 16 September 2021 was bought pay-as-bid without a clearing price and is
not included.

Volume-weighted clearing price, GBP/MW/h (calendar years; 2021 from 15 September, 2026 to
14 October):

| Year | DC low | DC high | DM low | DM high | DR low | DR high |
|---|---:|---:|---:|---:|---:|---:|
| 2021 | 16.56 | 6.01 | | | | |
| 2022 | 19.20 | 4.05 | 4.38 | 7.24 | 21.72 | 12.14 |
| 2023 | 2.81 | 3.46 | 3.99 | 2.31 | 10.21 | 0.09 |
| 2024 | 2.25 | 1.97 | 4.22 | 0.49 | 8.10 | −4.92 |
| 2025 | 3.93 | 2.55 | 6.51 | 2.00 | 13.17 | −2.51 |
| 2026 | 3.25 | 2.04 | 7.21 | −0.15 | 16.62 | −8.63 |

Median cleared volume per block in 2025: DC 1,180–1,221 MW, DM 300 MW, DR 480–500 MW (DR
low was 9 MW in 2022).

## `gb_response_utilisation.csv`

Average share of contracted MW each service delivers, per month from September 2021 to
September 2026 (61 months), which equals the energy it moves in MWh per MW per hour.
Columns: `month`, one column per service, and `samples` (valid one-second readings).

Source: NESO, *System frequency data*, one-second GB frequency per month,
<https://www.neso.energy/data-portal/system-frequency-data> (NESO Open Data Licence v1.0;
supported by National Energy SO Open Data). The monthly files (about 75 MB each) are read
and discarded; only these averages are kept.

Method: each reading is mapped to the delivery each service requires at that frequency,
from the delivery table in NESO's *Response Services Service Terms* (version 6, effective
31 July 2026, <https://www.neso.energy/document/384606/download>): nothing within
±0.015 Hz; DC rises linearly to 5% at ±0.2 Hz and to 100% at ±0.5 Hz; DM to 5% at ±0.1 Hz
and 100% at ±0.2 Hz; DR linearly to 100% at ±0.2 Hz. The table's check points (49.9 Hz:
DC 2.3%, DM 5%, DR 45.95%) are reproduced by OpenEnergy's tests. Readings outside
49–51 Hz are treated as bad samples (none were found).

Annual means: DC about 0.005–0.008, DM 0.02–0.04, DR 0.10–0.15 MWh per MW per hour, rising
from 2021 to 2026.

Known issues: this is the delivery a perfectly following unit would make; real units
also respond to their own metering and ramp limits. Months without frequency data use the
average of all months.
