# System model

The system model rebuilds the GB power system hour by hour from public data: which plants
run, what that costs, and the price it implies. It first replays 2015–2020 and checks the
result against what happened, then answers what-if questions on that tested base.

```bash
uv sync --extra system   # or: pip install 'openenergy[system]'  (PyPSA, for storage)
uv run openenergy system validate
uv run openenergy system run examples/gb-2019-system.yaml
```

## How it works

GB is one bus. Each hour, demand must equal supply:

- **Demand** is NESO's total generation for that hour.
- **Fixed at historic output:** nuclear, biomass, hydro, imports, pumped storage and
  "other". There is no open data to model continental prices or plant-level constraints,
  so these follow history (scaled in scenarios).
- **Wind and solar** are free to run and can be curtailed when supply exceeds demand.
- **Thermal plant** (CCGT, coal, and gas turbines with oil engines as "peaking") runs in
  order of short-run marginal cost. Each group's capacity (DUKES, interpolated between
  year ends) is derated by availability and split into equal tranches whose efficiencies
  spread around the fleet average:

$$c_{k,t} = \frac{p_{f,q(t)} + s_{f,t} + \lambda_t\, e_f}{\eta_k} + v$$

with fuel price $p$ (quarterly, DESNZ), carbon price support $s$ (HMRC), ETS price
$\lambda$ (EU ETS to 2020, UK ETS from 2021; one price per year from 1 April), emission
factor $e_f$ and efficiency
$\eta_k$. The price is the cost of the last unit needed, or the value of lost load
(default £6,000/MWh) if capacity runs out.

Without storage every hour is independent, so the merit order is the exact least-cost
dispatch. Added storage links hours together; then the model is solved as one linear
programme per year with [PyPSA](https://pypsa.org) and HiGHS. On 2019 data both give
identical prices and costs, and a year with storage solves in under two seconds.

| Assumption (default) | Why |
|---|---|
| 5 tranches per group; CCGT efficiency ±4 points, coal ±2 points around the DUKES average | Real fleets mix old and new units |
| Availability 0.9 | Peak gas output is 80–89% of CCGT plus gas-turbine capacity each year |
| Peaking plant costed as gas at 35% efficiency | Gas turbines and oil engines rarely run |
| Variable O&M 0 | No open source; configurable |

None of these is fitted to prices. Every one can be changed in a scenario's
`assumptions` section.

## Backcast: how close is it?

`openenergy system validate` replays April 2015 to September 2020 and compares with the
OPSD day-ahead price and NESO's actual gas and coal output.

| Year | Model £/MWh | Actual £/MWh | MAE | Corr. | p95 model / actual | Gas TWh model / actual | Coal TWh model / actual |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2015 (Apr–Dec) | 38.7 | 40.3 | 6.4 | 0.55 | 41 / 57 | 51 / 65 | 59.9 / 45.8 |
| 2016 | 35.8 | 40.5 | 9.6 | 0.32 | 46 / 65 | 146 / 127 | 9.6 / 28.0 |
| 2017 | 40.8 | 45.3 | 7.9 | 0.60 | 48 / 68 | 137 / 119 | 3.3 / 20.6 |
| 2018 | 50.0 | 57.4 | 9.6 | 0.49 | 58 / 80 | 123 / 115 | 7.3 / 15.4 |
| 2019 | 42.3 | 42.9 | 7.3 | 0.63 | 50 / 64 | 120 / 115 | 0.8 / 5.9 |
| 2020 (Jan–Sep) | 35.2 | 31.2 | 9.0 | 0.32 | 44 / 50 | 72 / 68 | 0.1 / 3.3 |

What the table shows:

- **Average prices are close.** The yearly mean is within £0.6–7.4/MWh, usually a little
  low. Fuel and carbon costs explain most of the price level.
- **Peaks are missed every year.** The 95th percentile is £6–22 below actual. A cost-only
  model has no scarcity pricing, start-up costs or bidding above cost, so its prices are
  much flatter than the market's (2019 standard deviation £4.5/MWh).
- **Coal left the model faster than it left the grid.** From 2016 the model runs less than
  half the coal that actually ran (2019: 0.8 against 5.9 TWh). Once carbon price support
  made coal dearer than most gas, a pure cost ranking switches it off; real coal plants
  kept running for reasons outside a cost-only model. In 2015 the model runs more coal
  than happened.
- **2020 is the only year the model is above actual**, by £4/MWh.

These are the model's limits, reported rather than tuned away. Use it for direction and
relative change between scenarios, not to forecast prices. [Unit commitment](#unit-commitment)
addresses the flat prices; the coal gap remains.

## Unit commitment

Real plants cannot follow demand freely: starting a unit costs money and wear, and a
running unit cannot go below a minimum stable output. So plants stay on overnight and sell
below cost rather than restart, and recover start costs over short peak runs. With
`system.commitment: true` (or `system validate --commitment`) the model includes this:

- Each CCGT, coal and peaking tranche is a number of identical units $n_{k,t}$ (whole
  numbers), each of size $U$, with output between $m U n_{k,t}$ and $U n_{k,t}$ (and at
  most the tranche's available capacity).
- Starting units costs $C\,U \max(0, n_{k,t} - n_{k,t-1})$, added to fuel and carbon cost.
- Each day is solved as a mixed-integer programme with HiGHS, seeing 24 hours beyond the
  day; units online and storage carry over to the next day.
- Load is shed only when available capacity runs out, as in the merit order.

| Technology | Unit size $U$ (MW) | Minimum stable output $m$ | Start cost $C$ (£/MW) |
|---|---:|---:|---:|
| CCGT | 500 | 40% | 34.29 |
| Coal | 500 | 18% | 40.53 |
| Peaking | 40 | 25% | 14.96 |

Unit size and minimum output are from the Danish Energy Agency's technology catalogue;
start costs are NREL's median warm-start costs, converted from 2011 US dollars (see
[Data sources](#data-sources)). They describe typical modern plant, not the GB fleet, and
none is fitted to prices.

Two prices come out:

- **Marginal** (`price: marginal`): the cost of one more MWh with the units online fixed.
  It ignores start costs, so it can sit below what a started unit needs.
- **Start** (`price: start`): each run of a unit spreads its start cost over the energy it
  produces in that run; the hour's price is the higher of the marginal price and the
  highest such cost-plus-start of any unit running.

### Backcast with unit commitment

April 2015 to September 2020, same data as above. Daily spread is the mean of each day's
highest minus lowest hourly price.

| Year | Daily spread: merit / UC marginal / UC start / actual | p95: merit / UC start / actual |
|---|---:|---:|
| 2015 (Apr–Dec) | 2.0 / 10.8 / 14.8 / 38.5 | 41 / 46 / 57 |
| 2016 | 3.7 / 13.6 / 17.4 / 68.9 | 46 / 53 / 65 |
| 2017 | 4.4 / 22.9 / 22.3 / 41.6 | 48 / 60 / 68 |
| 2018 | 4.1 / 27.3 / 23.9 / 40.6 | 58 / 65 / 80 |
| 2019 | 4.2 / 24.8 / 24.3 / 31.8 | 50 / 63 / 64 |
| 2020 (Jan–Sep) | 2.9 / 19.7 / 21.2 / 30.2 | 44 / 55 / 50 |

| Year | Mean: merit / UC marginal / UC start / actual | MAE: merit / UC marginal / UC start | Corr.: merit / UC marginal / UC start |
|---|---:|---:|---:|
| 2015 (Apr–Dec) | 38.7 / 38.6 / 41.5 / 40.3 | 6.4 / 6.0 / 6.9 | 0.55 / 0.52 / 0.39 |
| 2016 | 35.8 / 35.4 / 39.3 / 40.5 | 9.6 / 9.1 / 10.0 | 0.32 / 0.38 / 0.35 |
| 2017 | 40.8 / 40.1 / 44.8 / 45.3 | 7.9 / 7.9 / 7.6 | 0.60 / 0.59 / 0.57 |
| 2018 | 50.0 / 49.2 / 54.2 / 57.4 | 9.6 / 9.8 / 8.8 | 0.49 / 0.49 / 0.47 |
| 2019 | 42.3 / 41.6 / 46.0 / 42.9 | 7.3 / 7.1 / 8.0 | 0.63 / 0.59 / 0.57 |
| 2020 (Jan–Sep) | 35.2 / 34.6 / 38.1 / 31.2 | 9.0 / 8.8 / 10.6 | 0.32 / 0.39 / 0.40 |

Average 2019 price by hour (UTC), £/MWh:

| Hour | Merit order | UC marginal | UC start | Actual |
|---|---:|---:|---:|---:|
| 03:00 | 40.4 | 36.4 | 43.5 | 32.3 |
| 08:00 | 43.0 | 43.3 | 46.2 | 48.1 |
| 17:00 | 43.9 | 47.8 | 54.6 | 57.5 |
| 18:00 | 43.9 | 47.6 | 54.6 | 57.2 |

What the tables show:

- **Prices now move within the day.** The daily spread rises from £2–4 to £11–27, and
  the 2019 standard deviation from £4.5 to £8.7 (actual £11.7). Real spreads are still
  larger every year, most of all in 2016 (£69), whose spikes the model does not produce.
- **The two prices bracket the day.** The marginal price falls overnight close to the
  actual trough (2019 at 03:00: £36 against £32); the start price reaches the evening
  peak (£55 against £57) but stays high at night. Neither alone has both ends.
- **Peaks get closer.** The start price's 95th percentile is within £1 of actual in
  2019 and £8–15 below in 2015–2018, against £6–22 below for the merit order. In 2020 it
  is £5 above.
- **Fit is about the same.** The start price's mean is £3–4/MWh above the merit order's:
  to actual in 2015–2018, further in 2019 and 2020. MAE moves by under £2 either way;
  correlation is similar, except 2015, where the start price's falls to 0.39.
- **Coal still leaves too early** (2019: 0.8 TWh against 5.9 actual); start costs do not
  change the order of coal and gas.
- **Cost:** about a minute per year instead of under a second; about 10 unit starts a day
  in 2019.

So unit commitment fixes much of the missing daily shape without fitting anything, but
the model still has no scarcity pricing or bidding above cost. Commitment stays off by
default so earlier results and quick runs are unchanged.

## After 2020: gas crisis and coal exit

The system data runs to the end of 2025, and Ember's prices cover the years after OPSD
stops (see [Data](../data.md#gb-prices-after-2020)). The default backcast still ends in
September 2020, so the tables above do not change; later years are one flag away:

```bash
uv run openenergy system validate --start 2021-01-01 --end 2025-12-31 [--commitment --price start]
```

| Year | Model £/MWh merit / UC start | Actual £/MWh | MAE merit / UC | Corr. merit / UC | p95 merit / UC / actual | Daily spread merit / UC / actual | Gas TWh model / actual | Coal TWh model / actual |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021 | 83.5 / 88.0 | 117.8 | 38.5 / 35.8 | 0.58 / 0.59 | 143 / 152 / 258 | 7 / 34 / 146 | 102 / 107 | 10.2 / 5.0 |
| 2022 | 157.7 / 163.5 | 204.8 | 78.1 / 76.2 | 0.40 / 0.40 | 200 / 203 / 415 | 9 / 39 / 156 | 106 / 111 | 9.4 / 4.3 |
| 2023 | 121.1 / 125.9 | 94.1 | 32.9 / 36.1 | 0.52 / 0.52 | 140 / 149 / 156 | 7 / 33 / 70 | 86 / 87 | 3.5 / 2.8 |
| 2024 | 89.2 / 93.8 | 72.5 | 27.7 / 29.0 | 0.10 / 0.18 | 126 / 134 / 110 | 6 / 35 / 60 | 69 / 73 | 5.6 / 1.6 |
| 2025 | 87.5 / 92.1 | 80.7 | 18.7 / 19.8 | 0.57 / 0.52 | 106 / 115 / 123 | 6 / 37 / 67 | 77 / 77 | 0.0 / 0.0 |

Gas and coal TWh are from the merit order; unit commitment gives gas within 1 TWh of it.
No hour hit the value of lost load in any year.

What the table shows:

- **Gas volume is right; the gas price timing is not.** Modelled gas output is within
  5 TWh of actual every year. Prices are not: by quarter, the merit-order model is £42–102
  too low in four of the five quarters from July 2021 to September 2022, then £22–57 too
  high from April 2023 to March 2024, and within £12 from April 2024. This pattern is
  consistent with the fuel input: DESNZ's quarterly series is the price power producers
  paid, contracts included, which can lag the market (its Q1 2024 gas price, 4.46 p/kWh,
  is close to Q4 2023's 4.84 while the actual power price fell from £83 to £65). An open
  daily gas price would test this; none is bundled.
- **Spikes are missed.** In 2022 the actual 95th percentile is £415; the model reaches
  £200. Daily spreads in 2021–2022 averaged £146–156; unit commitment gets £34–39.
- **2024 is the weakest year** (correlation 0.10): early 2024 combines the lagging gas
  price with a coal price DESNZ reported at 1.5 p/kWh, so the model runs 5.6 TWh of coal
  where 1.6 ran before the last coal plant closed in September 2024.
- **2025 is the closest of these years**: mean within £7, correlation 0.57, no coal on
  either side.

The cost-based model explains the level of prices when fuel prices are stable and the
direction of the 2021–2022 rise, but not its size or timing. Read results for those years
as a lower bound on prices and spreads.

## What if: more wind

The same 2019 weather and demand with wind output scaled (`system.scale.wind`):

| Wind | Price mean | Price std | Curtailed (TWh) | Fossil CO2 (Mt) | System cost (£m) |
|---:|---:|---:|---:|---:|---:|
| ×1 | 42.25 | 4.52 | 0.0 | 44.3 | 4,914 |
| ×2 | 31.68 | 17.57 | 7.9 | 25.4 | 2,822 |
| ×3 | 21.85 | 20.38 | 38.7 | 15.3 | 1,700 |

Prices fall and spread out as more hours are set by free wind. Curtailment rises steeply
because nuclear, imports and biomass are held at historic output: the fixed floor is the
binding constraint, as in [System analysis](system.md).

## What if: storage in a windy system

At three times 2019 wind, adding 4-hour storage (`system.storage.<name>`):

| Storage | Curtailed (TWh) | Fossil CO2 (Mt) | System cost (£m) |
|---:|---:|---:|---:|
| none | 38.7 | 15.3 | 1,700 |
| 5 GW | 36.2 | 14.5 | 1,613 |
| 10 GW | 34.4 | 13.9 | 1,550 |
| 20 GW | 31.8 | 13.1 | 1,458 |

Each 5 GW recovers less curtailed wind than the one before. Storage here has perfect
foresight over the year, so these are best cases.

## A battery on modelled prices

A system scenario can value a battery on its own modelled prices, with the same
no-lookahead forecasts as on market data. For a 1 MW / 2 MWh battery (95% each way),
revenue per MW-year:

| Prices | Last-week forecast | Perfect foresight |
|---|---:|---:|
| Real 2019 market | 16,045 | 22,509 |
| Model, 2019 | −77 | 406 |
| Model with unit commitment, 2019, marginal price | 3,200 | 10,844 |
| Model with unit commitment, 2019, start price | 1,792 | 9,829 |
| Model, wind ×3 | 1,565 | 12,010 |
| Model, wind ×3 with 10 GW storage | −1,370 | 5,422 |

On the merit-order 2019 prices a battery earns almost nothing: the cost-based price is too
flat. With unit commitment the daily shape gives it £10–11k with perfect foresight, about
half the real market's £22.5k; the rest came from spikes and bidding the model leaves
out. With three times the wind, spreads open up and
perfect-foresight value reaches £12k; 10 GW of other storage then cuts it by more than
half. Forecasting on last week's prices fails on these spiky, weather-driven prices.

## What if: carbon price support

2016 with and without the GB carbon price support (`system.carbon_price_support`), at the
2016 EU ETS price and at £50/t:

| Carbon price support | EU ETS (£/t) | Price mean | Fossil CO2 (Mt) |
|---|---:|---:|---:|
| on | 4.14 | 35.64 | 61.5 |
| off | 4.14 | 25.97 | 101.1 |
| on | 50 | 55.96 | 58.5 |
| off | 50 | 48.07 | 58.7 |

With a low EU price, the support decides whether coal or gas runs first. In this model it
cut 2016 emissions by about 40 Mt and raised the average price by about £10/MWh. At £50/t
the EU price alone puts coal behind gas and the support adds cost without cutting
emissions. The backcast shows real coal fell more slowly than the model's, so treat the
size of the effect as an upper bound.

## Scenario reference

```yaml
name: gb-2019-wind3-storage
system:
  data: ../data/system                 # written by scripts/fetch_system_data.py
  prices:                              # optional: actual prices to compare, earlier files first
    - ../data/time_series/time_series_60min_singleindex_filtered.csv
    - ../data/prices/gb_day_ahead_ember.csv
  year: 2019                           # 2015 (from April) to 2025
  start: 2019-01-01                    # optional: a shorter window within the year
  end: 2019-03-31
  scale: {wind: 3.0, solar: 1.0}       # also nuclear, biomass, hydro, imports, other, pumped_storage
  capacity_mw: {coal: 0}               # replace installed ccgt, coal or peaking MW
  fuel_price_scale: {gas: 1.5}         # multiply gas or coal prices
  ets_gbp_per_t: 50                    # replace the ETS price (eu_ets_gbp_per_t also accepted)
  carbon_price_support: true
  storage:
    fleet: {power_mw: 10000, hours: 4, efficiency: 0.85}   # power_mw 0 leaves it out
  assumptions: {tranches: 5, availability: 0.9}
  voll: 6000
  backend: auto                        # auto, merit or pypsa
  commitment: false                    # true: start-up costs and minimum stable output
  lookahead_hours: 24                  # with commitment: hours seen beyond each day
  price: marginal                      # or start (needs commitment)
battery: {power_mw: 1, energy_mwh: 2}  # optional: value a battery on modelled prices
forecast: naive_last_week              # or perfect_foresight
```

Sweeps work on any setting, in the order given:

```bash
uv run openenergy sweep examples/gb-2019-system.yaml \
  --set system.scale.wind=1,2,3 --set system.storage.fleet.power_mw=0,10000 \
  --set system.storage.fleet.hours=4
```

`openenergy system run` writes `dispatch.csv` (hourly price, output by technology,
storage, curtailment, emissions) and `summary.json` with the data attributions.

## Data sources

| Input | Source | Licence |
|---|---|---|
| Generation by fuel, demand | NESO, [historic generation mix](https://www.neso.energy/data-portal/historic-generation-mix). Supported by National Energy SO Open Data | [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence) |
| Plant capacity and efficiency | DESNZ, [DUKES 2026](https://www.gov.uk/government/statistics/electricity-chapter-5-digest-of-united-kingdom-energy-statistics-dukes) tables 5.8 and 5.10 | [OGL v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) |
| Fuel prices | DESNZ, [Quarterly Energy Prices 3.2.1](https://www.gov.uk/government/statistical-data-sets/prices-of-fuels-purchased-by-major-power-producers) | OGL v3.0 |
| Carbon price support | HMRC, [Excise Notice CCL1/6](https://www.gov.uk/government/publications/excise-notice-ccl16-a-guide-to-carbon-price-floor) and [Climate Change Levy rates](https://www.gov.uk/guidance/climate-change-levy-rates) | OGL v3.0 |
| EU ETS (2015–2020) and UK ETS (2022–2025) price | World Bank, [Carbon Pricing Dashboard](https://carbonpricingdashboard.worldbank.org/compliance/price) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| UK ETS price 2021 | DESNZ, [determination of the UK ETS carbon price](https://www.gov.uk/government/publications/determinations-of-the-uk-ets-carbon-price) (mean 2021 auction price) | OGL v3.0 |
| Exchange rates | Source: European Central Bank, euro reference rates (USD-to-GBP cross rate derived by OpenEnergy) | ECB reuse terms |
| Unit size, minimum load | Danish Energy Agency, [Technology Data for Generation of Electricity and District Heating](https://ens.dk/en/analyses-and-statistics/technology-data-generation-electricity-and-district-heating) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Start-up costs | N. Kumar et al., [Power Plant Cycling Costs](https://www.osti.gov/biblio/1046269), NREL/SR-5500-55433, 2012, Table 1-1 (2011 US$, converted with ECB 2011 rates) | US government-sponsored report |
| Actual prices (validation) | [Open Power System Data](https://doi.org/10.25832/time_series/2020-10-06), GB day-ahead, to September 2020; then [Ember](https://ember-energy.org/data/european-wholesale-electricity-price-data/), converted at ECB daily rates | see [Data](../data.md); Ember CC BY 4.0 |

All accessed 10 October 2026. Full references, changes and known issues are on the
[Data](../data.md) page and in `data/system/README.md`; every `summary.json` repeats the
attribution for the data a run used. OpenEnergy is not affiliated with or endorsed by any
of these providers.

Storage dispatch uses PyPSA: T. Brown, J. Hörsch, D. Schlachtberger, *PyPSA: Python for
Power System Analysis*, Journal of Open Research Software 6(1), 2018,
<https://doi.org/10.5334/jors.188>.

## Limits

- One bus: no transmission constraints between Scotland and England.
- Unit commitment is optional and simplified: no minimum up or down times, ramp limits or
  start fuel, typical rather than GB-specific unit data, and one day planned at a time.
- Imports and other fixed profiles cannot respond to price.
- Fuel prices are quarterly averages of what power producers paid, which can lag market
  gas prices (most visible in 2021–2024); the ETS is one price per year (from 1 April).
- Storage optimisation has perfect foresight over the year.
- Emissions cover GB fossil plant only (no imports or biomass).
