# GB system data

Inputs for OpenEnergy's GB system model, written by `scripts/fetch_system_data.py`
(run with `uv run --with openpyxl python scripts/fetch_system_data.py`). Downloaded on
2026-10-10. OpenEnergy is not affiliated with or endorsed by any of the sources below.

## `generation_mix.csv`

Half-hourly GB generation by fuel, MW, 2015-01-01 00:00 to 2020-09-30 23:30 UTC
(100,800 rows, no gaps). Columns: `utc_timestamp` (start of the half-hour, UTC), `gas`,
`coal`, `nuclear`, `wind` (transmission-connected), `wind_emb` (embedded, estimated),
`hydro`, `imports`, `biomass`, `other`, `solar`, `storage`, and `generation` (their sum).

Source: National Energy System Operator (NESO), *Historic generation mix and carbon
intensity*, <https://www.neso.energy/data-portal/historic-generation-mix>.
Licence: [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence).
Supported by National Energy SO Open Data.

Changes: rows outside the period and the derived columns (carbon intensity, groupings and
percentages) dropped; `DATETIME` renamed `utc_timestamp` with a `Z` suffix; column names
lower-cased; values (all whole MW) written as integers, otherwise unchanged.

Known issues, from NESO's description: gaps are filled by NESO with seasonal
decomposition; net-negative values are set to zero, so `storage` is pumped-storage net
discharge only (pumping demand is absent) and `imports` is never negative (net exports are
absent); transmission-connected solar and batteries are counted in `other`.

## `fleet.csv`

GB major power producer capacity at the end of each year 2014-2020, MW, and thermal
efficiency (gross calorific value, fraction).

| Column | Source |
|--------|--------|
| `ccgt_mw`, `gas_turbine_mw`, `oil_engine_mw` | DUKES 2026 table 5.8.C, England and Wales + Scotland |
| `coal_mw`, `nuclear_mw`, `pumped_storage_mw` | DUKES 2026 table 5.8.A, England and Wales + Scotland |
| `ccgt_efficiency`, `coal_efficiency` | DUKES 2026 table 5.10.C (UK major power producers), percent / 100 |

Source: Department for Energy Security and Net Zero, *Digest of UK Energy Statistics
(DUKES): electricity*,
<https://www.gov.uk/government/statistics/electricity-chapter-5-digest-of-united-kingdom-energy-statistics-dukes>.
Contains public sector information licensed under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

DUKES uses grid export capacity where available, installed capacity otherwise.
Efficiencies are UK-wide fleet averages, not GB-only.

## `fuel_prices.csv`

Average prices of fuel bought by the major UK power producers, pence per kWh (gross
calorific value), by quarter 2014-2020, cash terms: `coal_p_per_kwh`, `oil_p_per_kwh`,
`gas_p_per_kwh`. Coal and gas prices exclude the Carbon Price Support levy.

Source: Department for Energy Security and Net Zero, *Quarterly Energy Prices* table 3.2.1,
<https://www.gov.uk/government/statistical-data-sets/prices-of-fuels-purchased-by-major-power-producers>.
Contains public sector information licensed under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

## `carbon_prices.csv`

One row per carbon year starting 1 April 2015-2020.

| Column | Source |
|--------|--------|
| `eu_ets_usd_per_t` | World Bank, [Carbon Pricing Dashboard](https://carbonpricingdashboard.worldbank.org/compliance/price), EU ETS price on 1 April, US$/tCO2e, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Recorded by hand from the dashboard (it blocks scripted downloads) |
| `fx_date`, `usd_per_eur`, `gbp_per_eur` | European Central Bank, [euro reference exchange rates](https://data.ecb.europa.eu/), on 1 April or the last business day before. Source: ECB |
| `cps_gas_gbp_per_kwh`, `cps_coal_gbp_per_gj` | HM Revenue & Customs, [Excise Notice CCL1/6: carbon price floor](https://www.gov.uk/government/publications/excise-notice-ccl16-a-guide-to-carbon-price-floor), carbon price support rates (gross calorific value). Open Government Licence v3.0 |

OpenEnergy converts the EU ETS price to GBP as
`eu_ets_usd_per_t / usd_per_eur * gbp_per_eur`. One price per year misses movements within
the year. Emission factors are taken from the carbon price support rates, which are set
at £18/tCO2 from April 2016: gas 0.1839 tCO2/MWh and coal 0.3096 tCO2/MWh of fuel.
