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
| `eu_ets_usd_per_t` | World Bank, [Carbon Pricing Dashboard](https://carbonpricingdashboard.worldbank.org/compliance/price), EU ETS price on 1 April (or latest before), US$/tCO2e, accessed 2026-10-10, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Recorded by hand from the dashboard's price-trend chart (it blocks scripted downloads); values unchanged |
| `fx_date`, `usd_per_eur`, `gbp_per_eur` | Source: European Central Bank, [euro foreign exchange reference rates](https://data.ecb.europa.eu/) (series EXR.D.GBP.EUR.SP00.A and EXR.D.USD.EUR.SP00.A), on 1 April or the last business day before. Stored unchanged; OpenEnergy derives the USD-to-GBP cross rate from them |
| `cps_gas_gbp_per_kwh`, `cps_coal_gbp_per_gj` | HM Revenue & Customs, [Excise Notice CCL1/6: carbon price floor](https://www.gov.uk/government/publications/excise-notice-ccl16-a-guide-to-carbon-price-floor), carbon price support rates (gross calorific value). Open Government Licence v3.0 |

OpenEnergy converts the EU ETS price to GBP as
`eu_ets_usd_per_t / usd_per_eur * gbp_per_eur`. One price per year misses movements within
the year. Emission factors are taken from the carbon price support rates, which are set
at £18/tCO2 from April 2016: gas 0.1839 tCO2/MWh and coal 0.3096 tCO2/MWh of fuel.

## `unit_parameters.csv`

Typical unit size, minimum stable output and start-up cost for the unit commitment model,
one row per thermal technology (`ccgt`, `coal`, `peaking`).

| Column | Source |
|--------|--------|
| `unit_mw`, `min_stable` | Danish Energy Agency, [Technology Data for Generation of Electricity and District Heating](https://ens.dk/en/analyses-and-statistics/technology-data-generation-electricity-and-district-heating), data sheet (May 2025 edition, <https://ens.dk/media/8615/download>), rows "Generating capacity for one unit" and "Minimum load". CCGT: sheet *05 Gas turb. CC, steam extract.*, 2020 upper bound for size, 2015 for minimum load. Coal: *01 Coal CHP*, 2015. Peaking: *04 Gas turb. simple cycle, L*, 2020 lower bound for size, 2015 for minimum load. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `start_cost_usd2011_per_mw` | N. Kumar, P. Besuner, S. Lefton, D. Agan and D. Hilleman, *Power Plant Cycling Costs*, NREL/SR-5500-55433, National Renewable Energy Laboratory, 2012, Table 1-1, median warm-start capital and maintenance cost: gas CC (CCGT), large sub-critical coal (coal), aero-derivative gas turbine (peaking). <https://www.osti.gov/biblio/1046269>. US government-sponsored report; values recorded by hand from the PDF, unchanged |
| `gbp_per_usd_2011` | Source: European Central Bank, [euro reference rates](https://data.ecb.europa.eu/), 2011 annual averages (series EXR.A.GBP.EUR.SP00.A and EXR.A.USD.EUR.SP00.A). OpenEnergy derives the USD-to-GBP cross rate |
| `start_cost_gbp_per_mw` | `start_cost_usd2011_per_mw * gbp_per_usd_2011`, not inflated to later years |

Known issues: these are typical published values, not GB-specific. The DEA sheets describe
modern Danish plant, so older GB coal units likely had higher minimum loads than the coal
CHP figure. DEA gives minimum load in percent; it is stored as a fraction. NREL's start costs are lower-bound
estimates of wear and exclude start fuel, and they are in 2011 dollars.
