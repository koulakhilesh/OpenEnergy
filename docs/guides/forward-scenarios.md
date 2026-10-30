# Forward scenarios

The [system model](system-model.md) rebuilds GB prices from the plants behind them. v4.0
adds two things that let it look forward, and v4.2 makes the links behave as they have
and adds unit commitment to them:

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
  interconnectors: links         # or {mode: links, hurdle_gbp_per_mwh: 5, availability: 1.0}
  commitment: true               # start-up costs and minimum stable output (marginal price)
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
prices start in October 2018, so links need a year from 2019. Links work with the merit
order, PyPSA (when storage is added) and unit commitment.

| Setting | Default | Meaning |
|---|---|---|
| `mode` | `fixed` | `fixed`: historic imports (as before v4.0); `links`: price-taking links |
| `hurdle_gbp_per_mwh` | 0 | added to import prices and taken off export prices |
| `availability` | `flows` | `flows`: each link's import and export share fitted from its actual flows (below); `gap`: a share that grows with the price gap, fitted from hourly flows (below); a number from 0 to 1 applies to every link |
| `prices` | `prices/europe_day_ahead_ember.csv` next to `data` | neighbours' hourly prices |

### Checked against history

`examples/interconnector_check.py` solves each year four ways and compares with GB's
actual day-ahead price and the actual flows (Elexon FUELHH): historic imports (fixed);
links at full capacity (full, the v4.0 and v4.1 default); links at their fitted
availability (links, the default from v4.2); and that with unit commitment (UC, marginal
price). Prices in £/MWh, flows in TWh:

| Year | Mean: actual / fixed / full / links / UC | Spread: actual / fixed / full / links / UC |
|---|---:|---:|
| 2019 | 42.9 / 42.3 / 42.4 / 42.7 / 42.2 | 31.8 / 4.2 / 8.5 / 6.1 / 25.9 |
| 2020 | 35.3 / 37.1 / 36.9 / 37.5 / 36.6 | 39.6 / 3.4 / 9.4 / 5.0 / 27.5 |
| 2021 | 117.8 / 83.5 / 86.7 / 85.3 / 85.0 | 146.4 / 7.1 / 25.2 / 14.0 / 40.1 |
| 2022 | 204.8 / 157.7 / 163.1 / 160.0 / 159.9 | 155.6 / 9.5 / 42.5 / 26.7 / 61.3 |
| 2023 | 94.1 / 121.1 / 110.9 / 117.2 / 116.8 | 70.0 / 7.4 / 45.5 / 30.1 / 61.8 |
| 2024 | 72.5 / 89.2 / 81.2 / 87.0 / 86.4 | 59.9 / 5.7 / 43.2 / 26.5 / 56.6 |
| 2025 | 80.7 / 87.5 / 82.4 / 86.6 / 86.3 | 67.5 / 6.2 / 41.1 / 25.2 / 52.0 |

| Year | Imports: actual / full / links / UC | Exports: actual / full / links / UC |
|---|---:|---:|
| 2019 | 25.0 / 34.6 / 21.5 / 21.7 | 3.7 / 9.9 / 4.5 / 4.2 |
| 2020 | 22.8 / 34.9 / 21.4 / 21.1 | 4.5 / 10.5 / 4.4 / 4.3 |
| 2021 | 29.2 / 29.9 / 19.0 / 18.7 | 4.4 / 28.1 / 12.5 / 12.4 |
| 2022 | 16.2 / 26.1 / 16.7 / 16.4 | 20.4 / 47.2 / 20.2 / 20.3 |
| 2023 | 33.5 / 64.7 / 42.8 / 43.2 | 10.1 / 11.1 / 4.7 / 4.2 |
| 2024 | 43.9 / 69.9 / 46.4 / 46.4 | 10.6 / 18.8 / 8.0 / 7.8 |
| 2025 | 44.0 / 69.0 / 45.4 / 45.4 | 14.8 / 23.4 / 11.2 / 11.1 |

At full capacity links trade far more than happened: imports up to 93% too high (2023)
and exports up to six times too high (2021). A price taker sees every hour's price gap as
profit; real flows are limited by outages, losses, ramping, capacity sold ahead, trading
on later markets and the neighbours' own supply. Each link's availability (below) brings
imports to within 7% of actual in 2020, 2022, 2024 and 2025; they are 14% low in 2019,
35% low in 2021 and 28% high in 2023. Exports are within 3% in 2020 and 2022, 22% high in
2019, almost three times too high in 2021, and a quarter to a half too low in 2023–2025.

Matching flows takes spread away: links at full capacity were importing the neighbours'
daily shape, which partly hid the model's own flat price (2025: 41.1 at full capacity,
25.2 at fitted availability). Unit commitment restores the shape on GB's own plant: the
spread is 69% to 94% of actual in 2019–2020 and 2023–2025 (27% and 39% in the 2021–2022
gas crisis, when quarterly fuel prices miss the market's swings). The mean is within £2 of
actual in 2019–2020, above it by £6–23 in 2023–2025 and well below it in 2021–2022 (see
the [system model](system-model.md#after-2020-gas-crisis-and-coal-exit)).

#### Link availability

`scripts/fit_interconnector_availability.py` sets each link's import and export
availability to the energy it actually moved over what a price taker at full capacity
would have moved on actual GB and neighbour prices, 2019–2025, capped at 1 (see
[Data](../data.md)). Fitted only on flows, never on prices. Fitted on 2019–2022 instead,
it gives 36.9 TWh of imports in 2024 against 43.9 actual (66.0 at full capacity), and
11.8 TWh of exports against 10.6. It is one number per link and direction, so it does not
respond to the size of the price gap.

#### Availability by price gap (v5.0)

Real links trade more of a bigger gap. From hourly flows (Elexon, 2019–2025) and actual
prices, `availability: gap` takes each link's share of capacity in hours whose gap was
£0–5, £5–10, £10–20, £20–40, £40–80 and over £80/MWh, made non-decreasing so each
link can be offered as six steps, the k-th at the neighbour's price plus the bin's lower
edge. Nemo Link, for example, imports 49% of its capacity at gaps under £5 and 90% above
£80; IFA2 exports 12% and 78%. The Irish links barely respond. The shares are in
`data/system/interconnector_gap_availability.csv`.

Tested the same way as the flat share (both fitted on 2019–2022 flows and actual prices,
links in service before 2023), it follows the hour-to-hour flows a little better and the
yearly energy a little worse:

| Year | Imports: actual / gap / flat | Exports: actual / gap / flat | Hourly correlation with actual flow: gap / flat |
|---|---:|---:|---:|
| 2023 | 33.5 / 24.4 / 26.7 | 10.1 / 8.0 / 10.0 | 0.47 / 0.43 |
| 2024 | 38.9 / 29.1 / 30.2 | 9.2 / 6.0 / 7.1 | 0.41 / 0.37 |
| 2025 | 38.9 / 28.6 / 29.3 | 9.5 / 6.2 / 7.4 | 0.46 / 0.43 |

In the model (links and unit commitment, 2023–2025) it moves the mean by under £1/MWh,
lowers the daily spread by 0.3 to 2.0 (2025: 50.0 against 52.0), cuts exports by a
fifth to a quarter, and changes the battery's perfect-foresight value by −7% to −2%
(planning on last week's prices it earns 6% to 26% more).
Because it does not beat the flat share out of sample, `flows` stays the default and
`gap` is an option. It matters most for the FES pathways below, where links are short at
scarcity.

#### Marginal or start price

With links and commitment, the marginal price is closer to history than the start price
in 2023, 2024 and 2025 on the mean, the daily spread, the hour-to-hour change and battery
value; the start price holds the night up at a running unit's cost plus its start cost.
The scenarios below use the marginal price. This is a choice between two un-fitted
definitions made on history. A 1 MW / 2 MWh battery (95% each way, £5/MWh wear), GBP per
MW-year, last week's prices / perfect foresight:

| Year | Actual | Links | Links + UC, marginal | Links + UC, start |
|---|---:|---:|---:|---:|
| 2023 | 36,075 / 45,748 | 1,765 / 11,838 | 8,660 / 28,350 | 3,974 / 20,397 |
| 2024 | 29,148 / 39,430 | 1,648 / 10,694 | 9,538 / 26,798 | 5,108 / 17,411 |
| 2025 | 36,148 / 44,927 | 949 / 10,413 | 11,623 / 26,483 | 4,864 / 16,955 |

With perfect foresight the model now gives 59% to 68% of the actual value; planning on
last week's prices, 24% to 33%.

A hurdle (`hurdle_gbp_per_mwh`) is still available but left at 0.

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
| Holistic Transition | 2030 | 86.3 | 72.0 | 36.8 | 35.7 | 24.6 | 38.9 | 8.7 | 12.4 | 68.0 |
| Holistic Transition | 2035 | 211.7 | 163.8 | 47.8 | 27.6 | 51.3 | 108.8 | 34.9 | 41.0 | 723.0 |
| Electric Engagement | 2030 | 74.3 | 58.0 | 36.3 | 37.0 | 28.4 | 40.1 | 11.6 | 12.2 | 9.7 |
| Electric Engagement | 2035 | 191.1 | 162.4 | 60.1 | 41.3 | 46.9 | 89.1 | 15.0 | 27.4 | 683.2 |
| Hydrogen Evolution | 2030 | 65.6 | 44.3 | 36.9 | 40.1 | 24.5 | 36.2 | 7.6 | 9.2 | 0 |
| Hydrogen Evolution | 2035 | 121.4 | 109.1 | 52.2 | 31.3 | 40.7 | 93.5 | 19.6 | 34.2 | 214.8 |
| Falling Behind | 2030 | 72.4 | 34.9 | 41.4 | 29.5 | 20.9 | 35.4 | 1.8 | 2.3 | 0 |
| Falling Behind | 2035 | 56.0 | 43.4 | 33.6 | 21.2 | 32.8 | 61.8 | 18.7 | 18.0 | 0 |
| Ten Year Forecast | 2030 | 66.3 | 38.6 | 37.2 | 22.9 | 24.2 | 46.8 | 6.2 | 7.4 | 0 |
| Ten Year Forecast | 2035 | 57.1 | 36.3 | 44.7 | 21.2 | 42.2 | 93.1 | 18.3 | 23.7 | 0 |
| Ten Year Outlook | 2030 | 73.8 | 32.0 | 43.2 | 42.1 | 19.6 | 34.0 | 1.6 | 7.4 | 0 |
| Ten Year Outlook | 2035 | 86.4 | 53.1 | 45.7 | 35.3 | 39.1 | 69.3 | 15.3 | 49.8 | 20.0 |

Settings since v4.2: links at each link's availability fitted from its flows, and unit
commitment (marginal price). For comparison, the model's own 2025 with the same settings
has a mean of £86.3/MWh and a spread of £52.0/MWh (actual £80.7 and £67.5).

Imports in 2030 are within 10% of FES's in four pathways and 40% and 62% above it in
Falling Behind and the Ten Year Forecast; in 2035 they are 1.3 to 2.1 times FES's (1.5 to
3.5 times before links were given their fitted availability). Exports are 44% to 71% of
FES's in every case: FES expects GB to export much more in windy hours than links that
behave as they did in 2019–2025 do. Curtailment is 22% to 104% of FES's.

Six cases leave demand unserved. The price sits at the £6,000/MWh value of lost load in
Holistic Transition 2035 for 174 hours on 11 days, Electric Engagement 2035 for 161 hours
on 10 days, Hydrogen Evolution 2035 for 73 hours on 5 days, and on one or two days in
Holistic Transition 2030, Electric Engagement 2030 and the Ten Year Outlook 2035.
Without those hours the means are £56–94/MWh. The cause is link availability, not unit
commitment. Holistic Transition, mean £/MWh and unserved GWh:

| Year | Full availability | Full + commitment | Fitted | Fitted + commitment |
|---|---:|---:|---:|---:|
| 2030 | 67.2, 0 | 67.6, 0 | 86.2, 68.0 | 86.3, 68.0 |
| 2035 | 77.9, 40.3 | 85.6, 50.5 | 170.8, 679.3 | 211.7, 723.0 |

The fitted availability holds on GB's tightest days in the record: on the 1% of days
with the highest GB price in 2019–2025, links imported 3% (ElecLink) to 42% (Nemo Link,
BritNed) of their capacity, below their fitted shares for every link but East West (39%
against 38%), because neighbours were often short at the same time. So derating links at stress is supported by the flows. What the model
leaves out is what FES counts on in those hours: demand response, new flexibility and
neighbours' own 2030s fleets. Read 2035 prices in these pathways as "this fleet is short
of firm capacity in 2025's weather when links behave as they have", not as a price
forecast. With every link at full capacity the same pathways shed load only in Holistic
Transition 2035 (50.5 GWh) and Electric Engagement 2035 (10.9 GWh)
(`availability: 1.0`). With `availability: gap`, where links trade more of the very large
gaps at scarcity, lost load falls by about a third but does not go away:

| Pathway and year | Unserved GWh, hours at £6,000: flows | gap | Mean £/MWh: flows | gap |
|---|---:|---:|---:|---:|
| Holistic Transition 2030 | 68.0, 25 | 47.0, 24 | 86.3 | 85.2 |
| Holistic Transition 2035 | 723.0, 174 | 510.4, 130 | 211.7 | 162.5 |
| Electric Engagement 2035 | 683.2, 161 | 480.4, 110 | 191.1 | 151.2 |
| Hydrogen Evolution 2035 | 214.8, 73 | 150.1, 44 | 121.4 | 95.4 |

### A battery on pathway prices

The same 1 MW / 2 MWh battery (95% each way, £5/MWh wear) on 358 days of each modelled
year, GBP per MW-year:

| Prices | Last week's prices | Perfect foresight |
|---|---:|---:|
| Actual 2025 | 36,148 | 44,927 |
| Model 2025, links + commitment | 11,623 | 26,483 |
| Holistic Transition 2030 / 2035 | 9,649 / 10,019 | 27,434 / 64,033 |
| Electric Engagement 2030 / 2035 | 4,853 / 14,261 | 22,640 / 70,217 |
| Hydrogen Evolution 2030 / 2035 | 6,318 / 12,138 | 18,393 / 47,247 |
| Falling Behind 2030 / 2035 | 3,892 / 4,311 | 12,106 / 16,368 |
| Ten Year Forecast 2030 / 2035 | 3,297 / 3,535 | 13,665 / 12,928 |
| Ten Year Outlook 2030 / 2035 | 2,528 / 4,259 | 9,967 / 19,929 |

Compare pathways with the model's own 2025, not with actual 2025: on modelled 2025 prices
the battery's perfect-foresight value is 59% of its actual value, and the model's daily
spread is 77% of the real one. Against that baseline, perfect-foresight value is 48% to
62% lower in Falling Behind 2030, the Ten Year Forecast and the Ten Year Outlook 2030,
15% to 38% lower in Electric Engagement and Hydrogen Evolution 2030, Falling Behind 2035
and the Ten Year Outlook 2035, and about the same in Holistic Transition 2030. The three
2035 pathways that rise far above it (Holistic Transition, Electric Engagement and
Hydrogen Evolution, 1.8 to 2.7 times) get most of that from the lost-load days above:
with perfect foresight over the full year, those days earn £49.4k of Holistic
Transition's £63.1k, £54.2k of Electric Engagement's £69.2k and £30.7k of Hydrogen
Evolution's £46.8k. Without lost-load days every pathway would be below the 2025
baseline: the six pathways with lost load earn £11.6k to £16.1k on their other days. A value that rests on a few days of lost load in one
weather year is not a robust result. Planning on last week's prices keeps 16% to 35% of
the perfect-foresight value, against 80% on actual 2025 prices and 44% on the model's own
2025.

## Limits

- One GB bus: no constraint between Scotland and England, which is where much FES
  curtailment happens.
- Links take the neighbours' actual prices for the weather year, so neighbours do not
  respond to GB, and their 2030s fleets are not modelled. New links are not added as new
  neighbours; FES interconnector growth scales the existing ten.
- Capacities from the register are today's; earlier limits on Moyle, IFA and BritNed are
  not modelled separately, only through each link's fitted availability (see
  [Data](../data.md)).
- Each link's availability is one number per direction for every hour and year (with
  `availability: gap`, one per price-gap bin); new FES capacity gets the existing links'
  shares.
- Ember gives one price for Norway and one for Denmark; GB's links land in southern Norway
  and western Denmark.
- The weather year's fuel and carbon prices are kept; storage efficiencies for FES
  batteries and long-duration storage are stated assumptions.
- With unit commitment (the published scenarios), storage is planned one day at a time
  seeing 24 hours ahead; without it, with perfect foresight over the year.

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
rates (source: ECB). FES and the register accessed 13 October 2026, flows and prices
30 October 2026 (daily and hourly flows); see [Data](../data.md) for the rest of
the system model's sources. OpenEnergy is not affiliated with or endorsed by NESO, Elexon,
Ember or the ECB.
