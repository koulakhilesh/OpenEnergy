# Forward scenarios

The [system model](system-model.md) rebuilds GB prices from the plants behind them. v4.0
adds two things that let it look forward:

- **Interconnector links** (`system.interconnectors: links`): GB's ten interconnectors
  trade with France, the Netherlands, Belgium, Norway, Denmark and Ireland at those
  markets' actual day-ahead prices, instead of holding imports at their historic output.
- **NESO Future Energy Scenarios** (`system.fes`): a FES pathway's capacities and demand
  for a year from 2025 to 2035, applied to a historic weather year.

```bash
uv sync --extra system
uv run openenergy system run examples/gb-2035-holistic.yaml
```

```yaml
name: gb-2035-holistic
system:
  data: ../data/system
  year: 2025                     # the weather year: weather, demand shape, fuel and carbon prices
  interconnectors: links         # or {mode: links, hurdle_gbp_per_mwh: 5, availability: 0.85}
  fes:
    pathway: Holistic Transition # also Electric Engagement, Hydrogen Evolution, Falling Behind,
                                 # Ten Year Forecast (FES 2025) and Ten Year Outlook (2026)
    year: 2035                   # 2025 to 2035, not before the weather year
    battery_efficiency: 0.85     # round trip; FES publishes none (stated assumption)
    ldes_efficiency: 0.75        # round trip for new long-duration storage (stated assumption)
battery: {power_mw: 1, energy_mwh: 2}
```

Results are "this fleet and demand in 2025's weather and markets", not price forecasts:
FES publishes no fuel or carbon price paths, so the weather year keeps its own.

## Interconnector links

Each built link in NESO's Interconnector Register is a price taker on GB's single bus: it
imports up to its import capacity whenever GB's price is above the neighbour's actual
day-ahead price (Ember, converted at ECB rates) plus a hurdle, and exports when GB's price
is below the neighbour's minus the hurdle. A link joins the system on the day it entered
service, read from Elexon's flows (Nemo Link 2019, IFA2 and NS Link 2021, ElecLink 2022,
Viking Link at the end of 2023, Greenlink 2025). Historic imports are dropped. Irish
prices start in October 2018, so links need a year from 2019. Unit commitment does not
support links yet.

| Setting | Default | Meaning |
|---|---|---|
| `mode` | `fixed` | `fixed`: historic imports (as before v4.0); `links`: price-taking links |
| `hurdle_gbp_per_mwh` | 0 | added to import prices and taken off export prices |
| `availability` | 1 | share of each link's capacity available |
| `prices` | `prices/europe_day_ahead_ember.csv` next to `data` | neighbours' hourly prices |

### Checked against history

`examples/interconnector_check.py` solves each year both ways and compares with GB's
actual day-ahead price and the actual flows (Elexon FUELHH). Prices in £/MWh (mean, and
mean daily highest minus lowest), flows in TWh:

| Year | Actual mean | Fixed | Links | Actual spread | Fixed | Links | Actual imports | Links | Actual exports | Links |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019 | 42.9 | 42.3 | 42.4 | 31.8 | 4.2 | 8.5 | 25.0 | 34.6 | 3.7 | 9.9 |
| 2020 | 35.3 | 37.1 | 36.9 | 39.6 | 3.4 | 9.4 | 22.8 | 34.9 | 4.5 | 10.4 |
| 2021 | 117.8 | 83.5 | 86.7 | 146.4 | 7.1 | 25.2 | 29.2 | 29.9 | 4.4 | 28.1 |
| 2022 | 204.8 | 157.7 | 163.1 | 155.6 | 9.5 | 42.5 | 16.2 | 26.0 | 20.4 | 47.2 |
| 2023 | 94.1 | 121.1 | 110.9 | 70.0 | 7.4 | 45.5 | 33.5 | 64.6 | 10.1 | 11.0 |
| 2024 | 72.5 | 89.2 | 81.2 | 59.9 | 5.7 | 43.2 | 43.9 | 70.0 | 10.6 | 18.8 |
| 2025 | 80.7 | 87.5 | 82.4 | 67.5 | 6.2 | 41.1 | 44.0 | 69.1 | 14.8 | 23.4 |

Links widen the daily spread in every year: from 2021 to between a sixth (2021) and almost
three-quarters (2024) of the actual spread, where fixed imports leave it at 5% to 13%. They
bring the mean closer to actual in every year too, by up to £10/MWh (2023). They also
trade far more than actually happened: imports are 38% to 93% too high in every year but
2021, and exports are too high in every year, six times too high in 2021. A price taker
sees every hour's price gap as profit; real flows are limited by losses, trading costs,
ramping, capacity sold ahead and the neighbours' own supply, none of which the model
sees.

A hurdle and lower availability move flows towards actual but take the spread down with
them (`--hurdle 5 --availability 0.85`):

| Year | Links mean | Links spread | Imports (actual) | Exports (actual) |
|---|---:|---:|---:|---:|
| 2022 | 162.7 | 35.9 | 20.7 (16.2) | 38.3 (20.4) |
| 2024 | 84.2 | 35.8 | 55.9 (43.9) | 11.2 (10.6) |
| 2025 | 84.6 | 33.3 | 53.4 (44.0) | 13.8 (14.8) |

Neither is fitted to prices: the defaults stay at no hurdle and full availability, and the
over-trading is reported rather than tuned away.

## FES pathways

`system.fes` scales the weather year's system by the ratio of the FES year to the weather
year in the same pathway, so every half-hour keeps its weather and demand shape:

| Weather-year input | Scaled by FES (target year / weather year) |
|---|---|
| Wind (transmission and embedded) | Offshore Wind + Onshore Wind capacity |
| Solar | Solar PV capacity |
| Nuclear, hydro | Nuclear; Hydro capacity |
| Biomass | Biomass + CCS Biomass capacity |
| CCGT and peaking capacity (DUKES) | Gas + CCS Gas + Hydrogen capacity |
| Coal | none (set to 0) |
| Demand | ED1 annual system demand |
| Interconnector capacity | Interconnectors capacity |
| Batteries | added in full: FES GW, hours = GWh / GW |
| Long-duration storage | added: FES increase over the weather year (GW, GWh) |

Pumped storage keeps its historic output. Hydrogen and CCS gas plant are costed as gas,
because there is no open cost data for them. The weather year has to be a year the FES
edition covers: from 2024 for FES 2025, from 2025 for the Ten Year Outlook. Any `scale` or
`capacity_mw` you set overrides the FES value.

### Results on 2025's weather

`scripts/build_scenario_prices.py` runs every pathway in 2030 and 2035 with default
settings (prices in £/MWh, energy in TWh, `fes` columns are NESO's own figures for the
same year):

| Pathway | Year | Mean | Spread | Imports | FES | Exports | FES | Curtailed | FES | Unserved GWh |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Holistic Transition | 2030 | 67.2 | 39.0 | 58.8 | 35.7 | 47.3 | 38.9 | 4.6 | 12.4 | 0 |
| Holistic Transition | 2035 | 77.9 | 71.8 | 79.1 | 27.6 | 97.3 | 108.8 | 17.1 | 41.0 | 40.3 |
| Electric Engagement | 2030 | 64.3 | 41.4 | 58.6 | 37.0 | 54.3 | 40.1 | 6.3 | 12.2 | 0 |
| Electric Engagement | 2035 | 75.4 | 59.8 | 98.3 | 41.3 | 88.0 | 89.1 | 7.5 | 27.4 | 10.9 |
| Hydrogen Evolution | 2030 | 67.2 | 43.0 | 58.9 | 40.1 | 47.0 | 36.2 | 4.7 | 9.2 | 0 |
| Hydrogen Evolution | 2035 | 64.8 | 43.8 | 83.9 | 31.3 | 78.3 | 93.5 | 10.1 | 34.2 | 0 |
| Falling Behind | 2030 | 71.6 | 36.3 | 64.5 | 29.5 | 41.3 | 35.4 | 1.7 | 2.3 | 0 |
| Falling Behind | 2035 | 59.9 | 42.1 | 54.4 | 21.2 | 63.2 | 61.8 | 10.0 | 18.0 | 0 |
| Ten Year Forecast | 2030 | 68.1 | 38.0 | 59.5 | 22.9 | 46.5 | 46.8 | 3.4 | 7.4 | 0 |
| Ten Year Forecast | 2035 | 61.4 | 37.5 | 73.6 | 21.2 | 79.9 | 93.1 | 8.5 | 23.7 | 0 |
| Ten Year Outlook | 2030 | 72.7 | 34.0 | 66.9 | 42.1 | 39.0 | 34.0 | 1.5 | 7.4 | 0 |
| Ten Year Outlook | 2035 | 62.4 | 36.0 | 74.4 | 35.3 | 74.1 | 69.3 | 7.5 | 49.8 | 0 |

For comparison, the model's own 2025 with links has a mean of £82.4/MWh and a spread of
£41.1/MWh (actual £80.7 and £67.5).

Exports land between 16% below and 35% above FES's in every case. Imports are 1.5 to 3.5
times FES's, the same over-trading seen in the backcast. Curtailment is 15% to 74% of
FES's: with links, surplus wind can leave through the interconnectors whenever a
neighbour's price is above zero. Two 2035 cases leave some demand unserved: Holistic
Transition for 9 hours on 2 days (40 GWh) and Electric Engagement for 2 hours on 1 day
(11 GWh). In those hours every gas plant and every link is at its limit and storage is
nearly empty; the price reaches the £6,000/MWh value of lost load.

### A battery on pathway prices

The same 1 MW / 2 MWh battery (95% each way, £5/MWh wear) on 358 days of each modelled
year, GBP per MW-year:

| Prices | Last week's prices | Perfect foresight |
|---|---:|---:|
| Actual 2025 | 36,148 | 44,927 |
| Model 2025, links | 7,348 | 20,035 |
| Holistic Transition 2030 / 2035 | 6,148 / 18,792 | 15,500 / 28,841 |
| Electric Engagement 2030 / 2035 | 7,769 / 21,679 | 17,756 / 30,695 |
| Hydrogen Evolution 2030 / 2035 | 9,504 / 8,986 | 19,539 / 19,180 |
| Falling Behind 2030 / 2035 | 6,302 / 6,391 | 15,110 / 18,044 |
| Ten Year Forecast 2030 / 2035 | 5,918 / 6,036 | 15,385 / 14,795 |
| Ten Year Outlook 2030 / 2035 | 5,472 / 6,370 | 12,781 / 14,243 |

Compare pathways with the model's own 2025, not with actual 2025: on modelled 2025 prices
the battery's perfect-foresight value is under half its actual value, and the model's
daily spread is about 60% of the real one. Against that baseline every pathway's 2030
value is lower, by 2% to 36%. Only Holistic Transition and Electric Engagement in 2035
rise above it, by 44% and 53%, and that rise comes from the scarcity days above: 2 days
earn £12.0k of Holistic Transition's £28.6k (perfect foresight, full year) and 1 day earns
£10.9k of Electric Engagement's £30.4k. Without them both would be below the 2025
baseline. A value that rests on one or two hours of lost load in one weather year is not a
robust result. Planning on last week's prices keeps under half of the perfect-foresight
value in 10 of the 12 cases, against 80% on actual 2025 prices.

## Limits

- One GB bus: no constraint between Scotland and England, which is where much FES
  curtailment happens.
- Links take the neighbours' actual prices for the weather year, so neighbours do not
  respond to GB, and their 2030s fleets are not modelled. New links are not added as new
  neighbours; FES interconnector growth scales the existing ten.
- Capacities from the register are today's; earlier limits on Moyle, IFA and BritNed are
  not modelled (see [Data](../data.md)).
- Ember gives one price for Norway and one for Denmark; GB's links land in southern Norway
  and western Denmark.
- The weather year's fuel and carbon prices are kept; storage efficiencies for FES
  batteries and long-duration storage are stated assumptions.
- Storage is optimised with perfect foresight over the year.

## Data sources

FES tables: NESO, *FES: Pathways to Net Zero 2025* and *2026 Ten Year Outlook*,
[ES1](https://www.neso.energy/data-portal/future-energy-scenario-electricity-supply-data-table-es1)
and [ED1](https://www.neso.energy/data-portal/fes-electricity-demand-summary-data-table-ed1);
interconnectors: NESO,
[Interconnector Register](https://www.neso.energy/data-portal/interconnector-register);
both under the [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence),
supported by National Energy SO Open Data. Flows: Elexon BMRS FUELHH, under the
[BMRS data licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/);
contains BMRS data © Elexon Limited copyright and database right 2026. Neighbouring prices:
Ember, [European Wholesale Electricity Price Data](https://ember-energy.org/data/european-wholesale-electricity-price-data/),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), converted with ECB reference
rates (source: ECB). All accessed 13 October 2026; see [Data](../data.md) for the rest of
the system model's sources. OpenEnergy is not affiliated with or endorsed by NESO, Elexon,
Ember or the ECB.
