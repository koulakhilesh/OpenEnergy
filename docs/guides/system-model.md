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

with fuel price $p$ (quarterly, DESNZ), carbon price support $s$ (HMRC), EU ETS price
$\lambda$ (World Bank, 1 April each year), emission factor $e_f$ and efficiency
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
relative change between scenarios, not to forecast prices.

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
| Model, wind ×3 | 1,565 | 12,010 |
| Model, wind ×3 with 10 GW storage | −1,370 | 5,422 |

On the modelled 2019 prices a battery earns almost nothing: the cost-based price is too
flat. Arbitrage revenue in 2019 came from the scarcity and bidding behaviour the model
leaves out, which is a finding in itself. With three times the wind, spreads open up and
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
  prices: ../data/time_series/time_series_60min_singleindex_filtered.csv  # optional
  year: 2019                           # 2015 (from April) to 2020 (to September)
  scale: {wind: 3.0, solar: 1.0}       # also nuclear, biomass, hydro, imports, other, pumped_storage
  capacity_mw: {coal: 0}               # replace installed ccgt, coal or peaking MW
  fuel_price_scale: {gas: 1.5}         # multiply gas or coal prices
  eu_ets_gbp_per_t: 50                 # replace the EU ETS price
  carbon_price_support: true
  storage:
    fleet: {power_mw: 10000, hours: 4, efficiency: 0.85}   # power_mw 0 leaves it out
  assumptions: {tranches: 5, availability: 0.9}
  voll: 6000
  backend: auto                        # auto, merit or pypsa
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
| Carbon price support | HMRC, [Excise Notice CCL1/6](https://www.gov.uk/government/publications/excise-notice-ccl16-a-guide-to-carbon-price-floor) | OGL v3.0 |
| EU ETS price | World Bank, [Carbon Pricing Dashboard](https://carbonpricingdashboard.worldbank.org/compliance/price) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Exchange rates | Source: European Central Bank, euro reference rates (USD-to-GBP cross rate derived by OpenEnergy) | ECB reuse terms |
| Actual prices (validation) | [Open Power System Data](https://doi.org/10.25832/time_series/2020-10-06), GB day-ahead | see [Data](../data.md) |

All accessed 10 October 2026. Full references, changes and known issues are on the
[Data](../data.md) page and in `data/system/README.md`; every `summary.json` repeats the
attribution for the data a run used. OpenEnergy is not affiliated with or endorsed by any
of these providers.

Storage dispatch uses PyPSA: T. Brown, J. Hörsch, D. Schlachtberger, *PyPSA: Python for
Power System Analysis*, Journal of Open Research Software 6(1), 2018,
<https://doi.org/10.5334/jors.188>.

## Limits

- One bus: no transmission constraints between Scotland and England.
- No unit commitment: no start-up costs, minimum stable output or ramp limits.
- Imports and other fixed profiles cannot respond to price.
- Fuel prices are quarterly averages; EU ETS is one price per year (from 1 April).
- Storage optimisation has perfect foresight over the year.
- Emissions cover GB fossil plant only (no imports or biomass).
