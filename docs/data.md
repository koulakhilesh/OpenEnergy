# Data

## Bundled extract

`data/time_series/time_series_60min_singleindex_filtered.csv` is an hourly extract of the
Open Power System Data time-series package covering Great Britain from 31 December 2014
to 30 September 2020. It contains the GB day-ahead price (in **GBP**/MWh), load, and solar
and wind generation and capacity. Timestamps are UTC (`utc_timestamp`). Version
2020-10-06 is still OPSD's latest time-series release (checked 13 October 2026), so
later years come from the sources below.

Of 2,101 days, 2,085 have a complete set of prices. The gaps are two-hour holes on the
spring clock change each year, two single missing hours, and four outages of about a day.
With the default `max_gap_hours: 2`, the short gaps are interpolated and the outages are
skipped.

Prices include genuine scarcity spikes, up to £999/MWh in September–November 2016;
they are kept.

## GB prices after 2020

OPSD's GB prices stop in September 2020. `data/prices/gb_day_ahead_ember.csv` carries the
GB hourly day-ahead price from 30 June 2016 to 5 October 2026 (90,000 hours, no gaps),
from Ember's European wholesale price data (CC BY 4.0), stored in EUR/MWh as published.
OpenEnergy converts each hour to GBP at the ECB reference rate for its day
(`data/prices/ecb_gbp_per_eur.csv`; the latest earlier rate on weekends and holidays).
Use it with `data: {source: ember, path: ...}`; `openenergy data update` downloads the
latest months into a user cache.

Where both exist (July 2016 to September 2020, 37,239 hours) the converted Ember price
matches OPSD with correlation 0.99996 and a mean absolute difference of £0.11/MWh, so the
two can be joined. The system model's backcast does exactly that: OPSD where it has a
price, Ember otherwise.

| Year | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Mean £/MWh | 45.3 | 57.4 | 42.9 | 35.3 | 117.8 | 204.8 | 94.1 | 72.5 | 80.7 |
| Mean daily spread £/MWh | 41.6 | 40.6 | 32.9 | 39.6 | 146.4 | 155.6 | 70.0 | 59.9 | 67.5 |

The series keeps 615 negative hours (down to −€60/MWh) and 38 hours at €1,000/MWh or more
(up to €2,576/MWh in 2021–2022). From 2021 Ember takes the UK price from EMR Settlement,
whose own reuse terms could not be read (the site blocks scripted access); OpenEnergy
relies on Ember's CC BY 4.0 publication and cites both.

## Neighbouring markets

`data/prices/europe_day_ahead_ember.csv` holds the hourly day-ahead prices of the six
markets GB's interconnectors reach (France, the Netherlands, Belgium, Norway, Denmark and
Ireland), EUR/MWh as published by Ember, from 1 January 2015 (Ireland from 1 October
2018) to 7 October 2026. The system model's [interconnector links](guides/forward-scenarios.md)
trade at these prices, converted to GBP like the GB price.

| Mean £/MWh (ECB rates) | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|
| GB | 42.9 | 35.3 | 117.8 | 204.8 | 94.1 | 72.5 | 80.7 |
| France | 34.6 | 28.7 | 93.4 | 235.1 | 84.4 | 48.9 | 52.2 |
| Netherlands | 36.1 | 28.7 | 88.1 | 206.2 | 83.5 | 65.3 | 74.3 |
| Belgium | 34.5 | 28.4 | 89.1 | 208.4 | 84.7 | 59.4 | 70.6 |
| Norway | 34.2 | 8.2 | 53.6 | 118.8 | 51.5 | 32.8 | 40.9 |
| Denmark | 34.2 | 23.5 | 75.4 | 184.0 | 73.7 | 59.8 | 69.9 |
| Ireland | 44.2 | 33.5 | 116.3 | 192.5 | 110.0 | 92.0 | 97.8 |

From 2023 to 2025 GB's mean price was above every neighbour's except Ireland's, which
helps explain why price-taking links import so much.

Known issues: Ember publishes one price for Norway and one for Denmark, without saying how
the bidding zones are combined; GB's links land in southern Norway (NO2) and western
Denmark (DK1). A few hours are blank on 31 July and 30 September 2026 (none before 2026).

## Renewable capacity factors

The extract also has hourly capacity-factor profiles (generation divided by installed
capacity) for `solar`, `wind`, `wind_onshore` and `wind_offshore`, from 2015 to
29 December 2019; OPSD stops publishing capacity after that.

In 233 hours the solar profile exceeds 1.0 (up to 1.367): reported capacity lags new
build, so generation divided by capacity overshoots. OpenEnergy clips profiles to [0, 1]
and reports how many values were clipped. The same lag pushes GB solar capacity factors to
15–18%, above the roughly 11% usually quoted; this changes absolute output but not
capture rates, which depend on the shape of the profile.

Other OPSD zones can be used by pointing `data.path` at a larger OPSD
`time_series_*_singleindex.csv`. OPSD publishes GB prices in GBP and all other zones in
EUR; OpenEnergy labels the currency accordingly.

## Carbon intensity

`data/carbon_intensity/gb_national.csv` holds GB national carbon intensity for every
half-hour from 1 January 2018 to 12 October 2026: NESO's forecast and its estimated
actual, in gCO2/kWh. It was downloaded with `scripts/fetch_carbon_intensity.py` and is
stored exactly as published; 179 half-hours the API did not return are left blank.

The archive has 804 half-hours without an actual value (18 runs, the longest about three
days) and 16 implausible forecasts (up to 13,579 gCO2/kWh). OpenEnergy treats any value
outside 0–1000 gCO2/kWh as missing and reports how many it rejected. Annual mean actual
intensity falls from 248 (2018) to 214 (2019), 180 (2020), 188 (2021), 183 (2022), 152
(2023), 125 (2024), 129 (2025) and 122 gCO2/kWh (2026 to 12 October).

These are **average** intensities of the whole system. Storage and renewables change the
**marginal** plant, whose emissions can differ; emissions results in OpenEnergy show
direction and rough scale, not causal impact.

## GB system data

`data/system/`, written by `scripts/fetch_system_data.py`, feeds the
[system model](guides/system-model.md):

| File | Contents | Source |
|---|---|---|
| `generation_mix.csv` | Half-hourly GB generation by fuel, MW, 2015-01-01 to 2025-12-31 (192,864 rows, no gaps) | NESO historic generation mix |
| `fleet.csv` | GB capacity at each year end 2014–2025 (CCGT, coal, gas turbines, oil engines, nuclear, pumped storage) and CCGT and coal efficiency | DUKES 5.8 and 5.10 |
| `fuel_prices.csv` | Quarterly coal, oil and gas prices paid by major power producers, 2014–2025 | DESNZ QEP 3.2.1 |
| `carbon_prices.csv` | EU ETS (2015–2020) and UK ETS (2021–2025) price on 1 April with ECB exchange rates, and carbon price support rates | World Bank, DESNZ (2021), ECB, HMRC |
| `unit_parameters.csv` | Unit size, minimum stable output and start-up cost for CCGT, coal and peaking plant (unit commitment) | Danish Energy Agency, NREL, ECB |
| `interconnectors.csv` | GB's ten built interconnectors: neighbour, import and export capacity (MW) | NESO Interconnector Register, 12 October 2026 |
| `interconnector_flows.csv` | Daily imports and exports per link, MWh, 2016-01-01 to 2026-10-12 | Elexon BMRS FUELHH |

The model's inputs stop at the latest complete calendar year, 2025 (checked 13 October
2026): DUKES publishes a year's fleet the following July, so 2026 has none yet, and the
2026 fuel and carbon prices that exist are not added until the year is complete, so every
model year has the same kind of inputs.

Known issues: NESO fills gaps by seasonal decomposition and sets net-negative values to
zero, so pumping demand and net exports are absent; transmission solar and batteries are
in "other". DUKES efficiencies are UK-wide averages. One ETS price per year misses moves
within the year (EU ETS 2018 rose from about €10 to €25; UK ETS 2021–2023 swung more). The
World Bank dashboard has no UK ETS price on 1 April 2021, before the first auction, so
2021 uses DESNZ's 2021 carbon price (mean auction price, £47.96/t). DESNZ suppresses some
coal prices from 2023 (carried forward) and gives no coal efficiency for 2025 (latest
earlier value used). Fuel prices are what power producers paid, including contracts
agreed earlier, so they lag market gas prices: see the
[system model](guides/system-model.md#after-2020-gas-crisis-and-coal-exit). Emission
factors (gas 0.1839, coal 0.3096 tCO2 per MWh of fuel) follow from the carbon price support
rates, which are set at £18/tCO2.

The interconnector register holds today's capacities only. Each link's first day in
service comes from its flows (the first flow in the first 14 days carrying at least a
fifth of its capacity, which skips commissioning tests): Nemo Link 2019-01-30, IFA2
2021-01-22, NS Link 2021-09-23, ElecLink 2022-05-23, Viking Link 2023-12-29 and Greenlink
2025-01-19. The flows also show limits the register does not (Moyle about 300 MW in
2016–2017, IFA about half its capacity in 2022, BritNed never above about 1,050 of
1,200 MW), so modelled link capacity is overstated in those periods.

## Future Energy Scenarios

`data/fes/` holds NESO's Future Energy Scenarios tables unchanged, written by
`scripts/fetch_fes.py`: the electricity supply (ES1) and demand summary (ED1) tables of
*FES: Pathways to Net Zero 2025* (pathways Holistic Transition, Electric Engagement,
Hydrogen Evolution and Falling Behind, plus the Ten Year Forecast; 2024–2050) and of the
*2026 Ten Year Outlook* (2025–2036). `system.fes` uses their capacities (MW), storage
(GWh) and annual system demand; see [forward scenarios](guides/forward-scenarios.md).
FES 2025's 2025 column is already a projection and differs by pathway; FES publishes no
fuel or carbon prices and no storage efficiencies.

`data/scenarios/` is model output, not source data: hourly modelled prices for each
pathway in 2030 and 2035 on 2025's weather (`fes_prices.csv`) and a summary next to FES's
own figures (`fes_summary.csv`), written by `scripts/build_scenario_prices.py` for the
[web app](guides/web-app.md). `data/app/` is model output too: per-MW battery results for
common requests (1, 2 and 4 hours, every year, response option and pathway), written by
`scripts/build_app_results.py` so the app answers at once.

## Frequency response

`data/response/`, written by `scripts/fetch_response_data.py`, feeds
[revenue stacking](guides/revenue-stacking.md):

- `gb_dynamic_response.csv`: the clearing price (GBP/MW/h) and cleared volume (MW) of
  each dynamic response service (DC, DM, DR; low and high) for every four-hour EFA block
  from 15 September 2021 22:00 to 14 October 2026 22:00 UTC (11,130 blocks, no gaps). DM
  and DR start on 26 March 2022.
- `gb_response_utilisation.csv`: for each month from September 2021 to September 2026, the
  average share of contracted MW each service delivers (MWh per MW per hour), from NESO's
  one-second GB frequency and the delivery envelopes in NESO's Response Services Service
  Terms (version 6). The raw frequency files (about 75 MB a month) are not bundled.

Known issues: Dynamic Containment before 16 September 2021 was bought pay-as-bid and is
not included; some prices are negative (mostly DM and DR high); utilisation is the
delivery of a unit following the envelope exactly. See `data/response/README.md`.

## Imbalance prices

`data/balancing/gb_system_prices.csv`, written by `scripts/fetch_system_prices.py`, holds
the GB system (imbalance) price for every half-hour from 2016 to 12 October 2026 (189,024
periods, 22
blank where Elexon's API returned nothing). GB has a single imbalance price, so the sell
and buy prices are equal; it is used by `examples/imbalance_value.py`.

## Attribution

**Prices, load and renewables**

> Open Power System Data. 2020. Data Package Time series. Version 2020-10-06.
> <https://doi.org/10.25832/time_series/2020-10-06>.
> (Primary data from various sources, for a complete list see URL).

The primary price and load data come from the ENTSO-E Transparency Platform.

**Carbon intensity**

> National Energy System Operator (NESO). Carbon Intensity API.
> <https://carbonintensity.org.uk/>. Licensed under
> [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/);
> [terms of use](https://github.com/carbon-intensity/terms).

OpenEnergy treats out-of-range values as missing and averages half-hours to the analysis
step; the bundled file itself is unchanged.

**Generation mix**

> National Energy System Operator (NESO). Historic generation mix and carbon intensity.
> <https://www.neso.energy/data-portal/historic-generation-mix> (accessed 10 October 2026).
> Licensed under the
> [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence).
> Supported by National Energy SO Open Data.

**Fleet capacity and efficiency**

> Department for Energy Security and Net Zero. Digest of UK Energy Statistics (DUKES)
> 2026, Chapter 5: table 5.8 (major power producers plant capacity, England and Wales,
> Scotland and Northern Ireland) and table 5.10 (plant loads, demand and efficiency).
> <https://www.gov.uk/government/statistics/electricity-chapter-5-digest-of-united-kingdom-energy-statistics-dukes>
> (accessed 10 October 2026).

**Fuel prices**

> Department for Energy Security and Net Zero. Quarterly Energy Prices, table 3.2.1:
> average prices of fuels purchased by the major UK power producers.
> <https://www.gov.uk/government/statistical-data-sets/prices-of-fuels-purchased-by-major-power-producers>
> (accessed 10 October 2026).

**Carbon price support**

> HM Revenue & Customs. Excise Notice CCL1/6: a guide to carbon price floor, section 2.3,
> <https://www.gov.uk/government/publications/excise-notice-ccl16-a-guide-to-carbon-price-floor>,
> and Climate Change Levy rates, <https://www.gov.uk/guidance/climate-change-levy-rates>
> (both accessed 10 October 2026).

**UK ETS price for 2021**

> Department for Energy Security and Net Zero (UK ETS Authority). UK ETS: carbon prices for
> use in civil penalties, 2021 and 2022.
> <https://www.gov.uk/government/publications/determinations-of-the-uk-ets-carbon-price>
> (accessed 10 October 2026).

The four UK government sources contain public sector information licensed under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

**EU ETS and UK ETS prices**

> World Bank. Carbon Pricing Dashboard: price of EU ETS (2015–2020) and UK ETS (2022–2025)
> allowances on 1 April each year.
> <https://carbonpricingdashboard.worldbank.org/compliance/price> (accessed
> 10 October 2026). Licensed under
> [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

**GB prices after 2020**

> Ember. European Wholesale Electricity Price Data, hourly, United Kingdom.
> <https://ember-energy.org/data/european-wholesale-electricity-price-data/> (accessed
> 10 October 2026). Licensed under
> [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Primary sources: ENTSO-E
> Transparency Platform and EMR Settlement.

OpenEnergy keeps Ember's EUR prices unchanged and converts them to GBP with ECB daily rates.

**Neighbouring day-ahead prices**

> Ember. European Wholesale Electricity Price Data, hourly, France, Netherlands, Belgium,
> Norway, Denmark and Ireland.
> <https://ember-energy.org/data/european-wholesale-electricity-price-data/> (accessed
> 13 October 2026). Licensed under
> [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Primary sources: ENTSO-E
> Transparency Platform and SEMOpx (Ireland).

**Interconnectors**

> National Energy System Operator (NESO). Interconnector Register (12 October 2026).
> <https://www.neso.energy/data-portal/interconnector-register> (accessed 13 October 2026).
> Licensed under the
> [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence).
> Supported by National Energy SO Open Data.

> Elexon. BMRS Insights API, generation by fuel type (FUELHH), interconnector flows,
> <https://bmrs.elexon.co.uk/> (accessed 13 October 2026). Reused under the
> [BMRS data licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/).
> Contains BMRS data © Elexon Limited copyright and database right 2026.

**Future Energy Scenarios**

> National Energy System Operator (NESO). FES: Pathways to Net Zero 2025 and 2026 Ten
> Year Outlook: Electricity Supply Data Table (ES1),
> <https://www.neso.energy/data-portal/future-energy-scenario-electricity-supply-data-table-es1>,
> and Electricity Demand Summary (ED1),
> <https://www.neso.energy/data-portal/fes-electricity-demand-summary-data-table-ed1>
> (accessed 13 October 2026). Licensed under the
> [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence).
> Supported by National Energy SO Open Data.

**Exchange rates**

> Source: European Central Bank, euro foreign exchange reference rates for GBP and USD.
> <https://data.ecb.europa.eu/> (accessed 10 October 2026).

OpenEnergy derives a USD-to-GBP cross rate from the two ECB rates to convert the World
Bank's US$ prices, and uses the daily GBP rate to convert Ember's EUR prices; the stored
rates are unchanged.

**Frequency response**

> National Energy System Operator (NESO). Dynamic Containment, Regulation and Moderation
> auction results, <https://www.neso.energy/data-portal/dynamic-containment-data>; Enduring
> Auction Capability (EAC) auction results,
> <https://www.neso.energy/data-portal/eac-auction-results>; System frequency data,
> <https://www.neso.energy/data-portal/system-frequency-data> (all accessed 13 October
> 2026). Licensed under the
> [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence).
> Supported by National Energy SO Open Data.

Delivery envelopes: NESO, *Response Services Service Terms*, version 6
(<https://www.neso.energy/document/384606/download>). Treatment of delivered energy: NESO,
*Dynamic Response A18 Submission Document* (2025,
<https://www.neso.energy/document/359721/download>). OpenEnergy keeps prices and volumes
unchanged, converts delivery times to UTC and reduces frequency to monthly averages.

**Imbalance prices**

> Elexon. BMRS Insights API, settlement system prices (DISEBSP),
> <https://bmrs.elexon.co.uk/> (accessed 13 October 2026). Reused under the
> [BMRS data licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/).
> Contains BMRS data © Elexon Limited copyright and database right 2026.

**Unit sizes and minimum loads**

> Danish Energy Agency. Technology Data for Generation of Electricity and District
> Heating, data sheet (May 2025 edition).
> <https://ens.dk/en/analyses-and-statistics/technology-data-generation-electricity-and-district-heating>
> (accessed 10 October 2026). Licensed under
> [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

**Start-up costs**

> N. Kumar, P. Besuner, S. Lefton, D. Agan and D. Hilleman. Power Plant Cycling Costs.
> NREL/SR-5500-55433. National Renewable Energy Laboratory, Golden, CO, 2012. Table 1-1,
> median warm-start costs. <https://www.osti.gov/biblio/1046269> (accessed 10 October 2026).

OpenEnergy converts the 2011 US$ values to GBP with 2011 annual average ECB reference rates
(source: European Central Bank) and does not inflate them; they are lower-bound costs for
typical plant, not GB-specific.

The system files keep source values unchanged apart from dropped rows and columns, GB
totals (England and Wales plus Scotland), integer MW and the start-cost conversion;
changes are listed in `data/system/README.md`. OpenEnergy is not affiliated with or
endorsed by Open Power System Data, NESO, Elexon, DESNZ, HMRC, the World Bank, the ECB,
the Danish Energy Agency, NREL or Ember.

## Software

The system model's storage dispatch uses PyPSA:

> T. Brown, J. Hörsch, D. Schlachtberger. PyPSA: Python for Power System Analysis.
> Journal of Open Research Software 6(1), 2018. <https://doi.org/10.5334/jors.188>.

Optimisation problems are solved with [HiGHS](https://highs.dev) (MIT licence).

Each data folder has a `README.md` with the full source, licence and known issues, and
every `summary.json` repeats the attribution for the data a run used.
