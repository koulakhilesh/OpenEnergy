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

with fuel price $p$ (gas: the daily System Average Price from 2018, DESNZ's quarterly price
paid by power producers before; coal and oil: quarterly, DESNZ), carbon price support $s$
(HMRC), ETS price $\lambda$ (EU ETS to 2020, UK ETS from 2021; one price per year from
1 April), emission factor $e_f$ and efficiency
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

Five tranches is enough: with links and unit commitment (2023–2025), the marginal price's
mean moves by under £1/MWh and its daily spread by under 5% between 5, 10 and 20 CCGT
tranches, while each step costs several times the solve time. More tranches only split
ties, so fewer hours repeat the previous hour's price.

## Backcast: how close is it?

`openenergy system validate` replays April 2015 to September 2020 and compares with the
OPSD day-ahead price and NESO's actual gas and coal output.

| Year | Model £/MWh | Actual £/MWh | MAE | Corr. | p95 model / actual | Gas TWh model / actual | Coal TWh model / actual |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2015 (Apr–Dec) | 38.7 | 40.3 | 6.4 | 0.55 | 41 / 57 | 51 / 65 | 59.9 / 45.8 |
| 2016 | 35.8 | 40.5 | 9.6 | 0.32 | 46 / 65 | 146 / 127 | 9.6 / 28.0 |
| 2017 | 40.8 | 45.3 | 7.9 | 0.60 | 48 / 68 | 137 / 119 | 3.3 / 20.6 |
| 2018 | 52.8 | 57.4 | 9.1 | 0.37 | 61 / 80 | 115 / 115 | 15.8 / 15.4 |
| 2019 | 38.1 | 42.9 | 7.3 | 0.69 | 54 / 64 | 119 / 115 | 1.7 / 5.9 |
| 2020 (Jan–Sep) | 26.7 | 31.2 | 8.4 | 0.54 | 35 / 50 | 72 / 68 | 0.0 / 3.3 |

What the table shows:

- **Average prices are a little low every year.** The yearly mean is £1.6–4.8/MWh below
  actual, and £4.5–4.8 below in each year from 2016. Fuel and carbon costs explain most
  of the price level. From 2018 the gas price is the daily wholesale price, which leaves
  out the network charges power stations pay; DESNZ's quarterly price paid includes them
  and contracts struck earlier, and put 2019 within £0.6 (below).
- **Peaks are missed every year.** The 95th percentile is £10–20 below actual. A
  cost-only model has no scarcity pricing, start-up costs or bidding above cost, so its
  prices are much flatter than the market's (2019 standard deviation £6.9/MWh).
- **Coal left the model faster than it left the grid**, except in 2018. In 2016, 2017,
  2019 and 2020 the model runs about a third or less of the coal that actually ran (2019:
  1.7 against 5.9 TWh). Once carbon price support made coal dearer than most gas, a pure cost
  ranking switches it off; real coal plants kept running for reasons outside a cost-only
  model. In 2015 the model runs more coal than happened.

These are the model's limits, reported rather than tuned away. Use it for direction and
relative change between scenarios, not to forecast prices. [Unit commitment](#unit-commitment)
addresses the flat prices; the coal gap remains.

### Daily or quarterly gas price

Until v6.0 the model priced gas with DESNZ's quarterly average of what power producers
paid. Since v6.0 it uses the daily System Average Price of gas (ONS, from National Gas
Transmission) from 2018, when the series begins; `system.gas_price: quarterly` (or
`system validate --gas-price quarterly`) restores the old input. Merit order, GB price
in £/MWh, daily / quarterly:

| Year | Mean (actual) | MAE | Correlation | p95 (actual) |
|---|---:|---:|---:|---:|
| 2018 | 52.8 / 50.0 (57.4) | 9.1 / 9.6 | 0.37 / 0.49 | 61 / 58 (80) |
| 2019 | 38.1 / 42.3 (42.9) | 7.3 / 7.3 | 0.69 / 0.63 | 54 / 50 (64) |
| 2020 (Jan–Sep) | 26.7 / 35.2 (31.2) | 8.4 / 9.0 | 0.54 / 0.32 | 35 / 44 (50) |
| 2021 | 98.2 / 83.5 (117.8) | 26.6 / 38.5 | 0.65 / 0.58 | 192 / 143 (258) |
| 2022 | 172.8 / 157.7 (204.8) | 46.4 / 78.1 | 0.81 / 0.40 | 298 / 200 (415) |
| 2023 | 101.8 / 121.1 (94.1) | 19.1 / 32.9 | 0.67 / 0.52 | 141 / 140 (156) |
| 2024 | 79.7 / 89.2 (72.5) | 17.3 / 27.7 | 0.53 / 0.10 | 102 / 126 (110) |
| 2025 | 83.8 / 87.5 (80.7) | 17.3 / 18.7 | 0.55 / 0.57 | 115 / 106 (123) |

The daily price fixes the timing: through the gas crisis and its aftermath the error
falls by 31–42% (2021–2024) and the correlation with actual prices rises, most in 2022
(0.40 to 0.81) and 2024 (0.10 to 0.53). It does not fix the size of the swings: the
model's daily spread stays a small fraction of the market's (below). Before the crisis it
is mixed: the modelled mean is £4.2 lower than with the quarterly price in 2019 and £8.5
lower in 2020 (£2.8 higher in 2018), so the quarterly price is closer on the 2019 mean
and has the better 2018 correlation. Both inputs are published statistics; neither is
adjusted to fit prices.

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

April 2015 to September 2020, same data as above (`system validate --commitment`, with
`--price start` for the start price). Daily spread is the mean of each day's highest minus
lowest hourly price, £/MWh.

| Year | Daily spread: merit / UC marginal / UC start / actual | p95: merit / UC start / actual |
|---|---:|---:|
| 2015 (Apr–Dec) | 2 / 11 / 15 / 38 | 41 / 46 / 57 |
| 2016 | 4 / 14 / 17 / 69 | 46 / 53 / 65 |
| 2017 | 4 / 23 / 22 / 42 | 48 / 60 / 68 |
| 2018 | 4 / 25 / 23 / 41 | 61 / 69 / 80 |
| 2019 | 4 / 22 / 21 / 32 | 54 / 60 / 64 |
| 2020 (Jan–Sep) | 2 / 16 / 17 / 30 | 35 / 44 / 50 |

| Year | Mean: merit / UC marginal / UC start / actual | MAE: merit / UC marginal / UC start | Corr.: merit / UC marginal / UC start |
|---|---:|---:|---:|
| 2015 (Apr–Dec) | 38.7 / 38.6 / 41.5 / 40.3 | 6.4 / 6.0 / 6.9 | 0.55 / 0.52 / 0.39 |
| 2016 | 35.8 / 35.4 / 39.3 / 40.5 | 9.6 / 9.1 / 10.0 | 0.32 / 0.38 / 0.35 |
| 2017 | 40.8 / 40.1 / 44.8 / 45.3 | 7.9 / 7.8 / 7.6 | 0.60 / 0.59 / 0.57 |
| 2018 | 52.8 / 52.1 / 56.8 / 57.4 | 9.1 / 9.0 / 8.9 | 0.37 / 0.46 / 0.43 |
| 2019 | 38.1 / 37.4 / 41.5 / 42.9 | 7.3 / 7.3 / 6.8 | 0.69 / 0.70 / 0.68 |
| 2020 (Jan–Sep) | 26.7 / 26.2 / 29.3 / 31.2 | 8.4 / 8.3 / 7.7 | 0.54 / 0.58 / 0.57 |

Average 2019 price by hour (UTC), £/MWh (`system validate --start 2019-01-01 --end
2019-12-31 --out DIR`, `hourly.csv`):

| Hour | Merit order | UC marginal | UC start | Actual |
|---|---:|---:|---:|---:|
| 03:00 | 36.4 | 32.4 | 39.4 | 32.3 |
| 08:00 | 38.6 | 39.0 | 41.8 | 48.1 |
| 17:00 | 39.4 | 42.9 | 49.4 | 57.5 |
| 18:00 | 39.5 | 42.6 | 48.5 | 57.2 |

What the tables show:

- **Prices now move within the day.** The daily spread rises from £2–4 to £11–25, and
  the 2019 standard deviation from £6.9 to £9.2 with the marginal price and £9.7 with the
  start price (actual £11.7). Real spreads are still larger every year, most of all in
  2016 (£69), whose spikes the model does not produce.
- **The two prices bracket the day.** The marginal price matches the overnight trough
  (2019 at 03:00: £32.4 against £32.3); the start price comes closest at the evening peak
  (17:00: £49 against £58) but stays high at night (£39). Neither alone has both ends.
- **Peaks get closer.** The start price's 95th percentile is £4–12 below actual, against
  £10–20 below for the merit order.
- **The start price fits the level better.** It is £2.6–4.0/MWh above the merit order,
  which brings its mean within £2 of actual every year. MAE moves by under £1 either way;
  correlation is similar, except 2015, where the start price's falls to 0.39.
- **Coal still leaves too early** (2019: 1.8 TWh against 5.9 actual); start costs do not
  change the order of coal and gas.
- **Cost:** about a minute per year instead of under a second.

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
| 2021 | 98.2 / 103.0 | 117.8 | 26.6 / 25.2 | 0.65 / 0.66 | 192 / 201 / 258 | 13 / 41 / 146 | 97 / 107 | 15.2 / 5.0 |
| 2022 | 172.8 / 178.2 | 204.8 | 46.4 / 44.2 | 0.81 / 0.81 | 298 / 307 / 415 | 17 / 51 / 156 | 96 / 111 | 19.8 / 4.3 |
| 2023 | 101.8 / 106.2 | 94.1 | 19.1 / 20.5 | 0.67 / 0.67 | 141 / 150 / 156 | 7 / 30 / 70 | 89 / 87 | 0.9 / 2.8 |
| 2024 | 79.7 / 84.2 | 72.5 | 17.3 / 18.4 | 0.53 / 0.54 | 102 / 109 / 110 | 5 / 32 / 60 | 72 / 73 | 2.2 / 1.6 |
| 2025 | 83.8 / 88.3 | 80.7 | 17.3 / 17.4 | 0.55 / 0.56 | 115 / 123 / 123 | 6 / 36 / 67 | 77 / 77 | 0.0 / 0.0 |

Gas and coal TWh are from the merit order; unit commitment gives gas within 1 TWh of it.

What the table shows:

- **With the daily gas price the timing is right; the coal is not.** The model's prices
  now follow the crisis (correlation 0.81 in 2022; 0.40 with quarterly gas, see
  [above](#daily-or-quarterly-gas-price)). At crisis gas prices the model's remaining coal
  plant is cheaper than gas, so in 2021 and 2022 it burns 15.2 and 19.8 TWh of coal where
  5.0 and 4.3 ran, and 10–15 TWh less gas than actual. From 2023 gas output is within
  2 TWh of actual.
- **Spikes are missed.** In 2022 the actual 95th percentile is £415; the model reaches
  £298, or £307 with unit commitment. Daily spreads in 2021–2022 averaged £146–156; unit
  commitment gets £41–51.
- **From 2023 the mean is £3–12 above actual** (merit order £3–8, start price £8–12),
  with correlation 0.53–0.67 and the 95th percentile within £15 of actual.

The cost-based model now explains the level and timing of prices through the gas crisis
from fuel prices alone, but not the size of their daily swings. Read results for 2021–2022
as a lower bound on spreads.

## What if: more wind

The same 2019 weather and demand with wind output scaled (`system.scale.wind`):

| Wind | Price mean | Price std | Curtailed (TWh) | Fossil CO2 (Mt) | System cost (£m) |
|---:|---:|---:|---:|---:|---:|
| ×1 | 38.04 | 6.92 | 0.0 | 44.8 | 4,518 |
| ×2 | 28.87 | 16.71 | 7.9 | 25.8 | 2,638 |
| ×3 | 20.11 | 19.20 | 38.7 | 15.6 | 1,614 |

Prices fall and spread out as more hours are set by free wind. Curtailment rises steeply
because nuclear, imports and biomass are held at historic output: the fixed floor is the
binding constraint, as in [System analysis](system.md).

## What if: storage in a windy system

At three times 2019 wind, adding 4-hour storage (`system.storage.<name>`):

| Storage | Curtailed (TWh) | Fossil CO2 (Mt) | System cost (£m) |
|---:|---:|---:|---:|
| none | 38.7 | 15.6 | 1,614 |
| 5 GW | 36.2 | 14.8 | 1,535 |
| 10 GW | 34.4 | 14.2 | 1,478 |
| 20 GW | 31.8 | 13.4 | 1,393 |

Each 5 GW recovers less curtailed wind than the one before. Storage here has perfect
foresight over the year, so these are best cases.

## A battery on modelled prices

A system scenario can value a battery on its own modelled prices, with the same
no-lookahead forecasts as on market data. For a 1 MW / 2 MWh battery (95% each way),
revenue per MW-year:

| Prices | Last-week forecast | Perfect foresight |
|---|---:|---:|
| Real 2019 market | 16,055 | 22,509 |
| Model, 2019 | −129 | 322 |
| Model with unit commitment, 2019, marginal price | 2,730 | 10,043 |
| Model with unit commitment, 2019, start price | 1,334 | 8,772 |
| Model, wind ×3 | 1,137 | 11,943 |
| Model, wind ×3 with 10 GW storage | −505 | 5,331 |

On the merit-order 2019 prices a battery earns almost nothing: the cost-based price is too
flat. With unit commitment the daily shape gives it £9–10k with perfect foresight, under
half the real market's £22.5k; the rest came from spikes and bidding the model leaves
out. With three times the wind, spreads open up and
perfect-foresight value reaches £12k; 10 GW of other storage then cuts it by more than
half. Forecasting on last week's prices fails on these spiky, weather-driven prices.

## What if: carbon price support

2016 with and without the GB carbon price support (`system.carbon_price_support`), at the
2016 EU ETS price and at £50/t:

| Carbon price support | EU ETS (£/t) | Price mean | Fossil CO2 (Mt) |
|---|---:|---:|---:|
| on | 4.14 | 35.77 | 61.5 |
| off | 4.14 | 26.11 | 101.1 |
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
  interconnectors: fixed               # or links (from 2019; see Forward scenarios)
  fes: {pathway: Holistic Transition, year: 2035}   # optional, needs links
battery: {power_mw: 1, energy_mwh: 2}  # optional: value a battery on modelled prices
forecast: naive_last_week              # or perfect_foresight
```

`interconnectors` and `fes` are described in [Forward scenarios](forward-scenarios.md).

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
| Daily gas price (from 2018) | ONS, [System Average Price (SAP) of gas](https://www.ons.gov.uk/economy/economicoutputandproductivity/output/datasets/systemaveragepricesapofgas), from National Gas Transmission (accessed 30 October 2026) | OGL v3.0 |
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
- Imports and other fixed profiles cannot respond to price, unless interconnectors are
  `links` ([Forward scenarios](forward-scenarios.md)), which take the neighbours' prices
  as given and trade up to each link's availability fitted from its flows. Links work with
  unit commitment from v4.2.
- Gas is priced at the daily wholesale price from 2018 (without the network charges power
  stations pay) and the quarterly price paid before; coal and oil are quarterly; the ETS
  is one price per year (from 1 April).
- Storage optimisation has perfect foresight over the year.
- Emissions cover GB fossil plant only (no imports or biomass).
