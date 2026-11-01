# Forward scenarios

The [system model](system-model.md) rebuilds GB prices from the plants behind them. v4.0
adds two things that let it look forward, and v4.2 makes the links behave as they have
and adds unit commitment to them:

- **Interconnector links** (`system.interconnectors: links`): GB's ten interconnectors
  trade with France, the Netherlands, Belgium, Norway, Denmark and Ireland at those
  markets' actual day-ahead prices, instead of holding imports at their historic output.
- **NESO Future Energy Scenarios** (`system.fes`): a FES pathway's capacities and demand
  for a year from 2025 to 2035, applied to a historic weather year.

v6.0 makes each FES system secure to GB's reliability standard before valuing anything on
it, and asks how much storage GB can use ([below](#how-much-storage-can-gb-use)).

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
    adequacy: secure             # add the least firm capacity meeting lole_hours (v6.0); or as_modelled
    lole_hours: 3                # GB's reliability standard: hours a year with unserved energy
    # firm_mw: 8000              # or add exactly this much firm capacity, no search
    battery_scale: 1.0           # multiply the FES battery fleet's power
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
price). Prices in £/MWh, flows in TWh, with the daily gas price (v6.0):

| Year | Mean: actual / fixed / full / links / UC | Spread: actual / fixed / full / links / UC |
|---|---:|---:|
| 2019 | 42.9 / 38.0 / 38.8 / 38.7 / 38.4 | 31.8 / 3.6 / 8.6 / 6.1 / 23.8 |
| 2020 | 35.3 / 30.3 / 30.9 / 30.9 / 30.4 | 39.6 / 3.0 / 8.4 / 4.9 / 24.9 |
| 2021 | 117.8 / 98.2 / 99.3 / 99.4 / 99.1 | 146.4 / 12.5 / 27.9 / 18.3 / 44.5 |
| 2022 | 204.8 / 172.8 / 179.3 / 176.2 / 176.2 | 155.6 / 16.6 / 41.8 / 28.1 / 59.9 |
| 2023 | 94.1 / 101.8 / 97.0 / 100.1 / 99.9 | 70.0 / 6.6 / 40.6 / 26.7 / 53.6 |
| 2024 | 72.5 / 79.7 / 74.1 / 78.2 / 77.8 | 59.9 / 5.3 / 37.4 / 23.4 / 52.5 |
| 2025 | 80.7 / 83.8 / 79.9 / 83.3 / 83.0 | 67.5 / 6.0 / 39.1 / 23.8 / 51.0 |

| Year | Imports: actual / full / links / UC | Exports: actual / full / links / UC |
|---|---:|---:|
| 2019 | 25.0 / 28.5 / 17.8 / 17.5 | 3.7 / 15.9 / 7.2 / 7.1 |
| 2020 | 22.8 / 26.3 / 16.4 / 15.7 | 4.5 / 19.2 / 8.2 / 8.3 |
| 2021 | 29.2 / 37.9 / 24.1 / 24.1 | 4.4 / 19.8 / 8.9 / 8.7 |
| 2022 | 16.2 / 26.3 / 16.6 / 16.0 | 20.4 / 46.8 / 19.9 / 20.1 |
| 2023 | 33.5 / 54.9 / 36.7 / 37.0 | 10.1 / 20.7 / 9.1 / 8.6 |
| 2024 | 43.9 / 69.4 / 46.3 / 46.5 | 10.6 / 19.3 / 8.3 / 7.9 |
| 2025 | 44.0 / 65.5 / 43.2 / 42.9 | 14.8 / 27.2 / 13.2 / 13.2 |

At full capacity links trade far more than happened: imports up to 64% too high (2023)
and exports up to 4.5 times too high (2021). A price taker sees every hour's price gap as
profit; real flows are limited by outages, losses, ramping, capacity sold ahead, trading
on later markets and the neighbours' own supply. Each link's availability (below) brings
imports to within 5% of actual in 2022, 2024 and 2025; they are 10% high in 2023 and
17–29% low in 2019–2021. Exports are within 2% in 2022 and 10–22% low in 2023–2025, but
about twice actual in 2019–2021: with the daily gas price the modelled GB price in those
years is lower than actual, so the links export more and import less than they did.

Matching flows takes spread away: links at full capacity were importing the neighbours'
daily shape, which partly hid the model's own flat price (2025: 39.1 at full capacity,
23.8 at fitted availability). Unit commitment restores the shape on GB's own plant: the
spread is 63% to 88% of actual in 2019–2020 and 2023–2025 (30% and 38% in the 2021–2022
gas crisis, even with the daily gas price). The mean is £4.5–4.9 below actual in
2019–2020, £2–6 above it in 2023–2025 and £19–29 below it in 2021–2022 (see the
[system model](system-model.md#after-2020-gas-crisis-and-coal-exit)).

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
lowers the daily spread by 2.1 to 3.4 (2025: 47.9 against 51.0), cuts exports by about a
quarter, and changes the battery's perfect-foresight value by −10% to −7% (planning on
last week's prices it earns 6% to 23% more).
Because it does not beat the flat share out of sample, `flows` stays the default and
`gap` is an option. It matters most for the FES pathways below, where links are short at
scarcity.

#### Marginal or start price

With links and commitment, the marginal price is closer to history than the start price
in 2023, 2024 and 2025 on the mean, the daily spread and battery value; the start price holds the night up at a running unit's cost plus its start cost.
The scenarios below use the marginal price. This is a choice between two un-fitted
definitions made on history. A 1 MW / 2 MWh battery (95% each way, £5/MWh wear), GBP per
MW-year, last week's prices / perfect foresight (actual: the whole year; model: 358 or 359
days, from the second week):

| Year | Actual | Links | Links + UC, marginal | Links + UC, start |
|---|---:|---:|---:|---:|
| 2023 | 36,362 / 46,440 | 1,604 / 9,275 | 10,982 / 25,701 | 4,228 / 15,228 |
| 2024 | 29,048 / 39,304 | 1,643 / 9,234 | 9,282 / 25,553 | 4,425 / 15,308 |
| 2025 | 36,208 / 44,974 | 648 / 9,728 | 11,293 / 26,038 | 4,384 / 15,723 |

With perfect foresight the model gives 55% to 65% of the actual value; planning on
last week's prices, 30% to 32%.

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
same year; firm capacity is what the secure top-up added, below):

| Pathway | Year | Mean | Spread | Imports | FES | Exports | FES | Curtailed | FES | Firm added (GW) | Unserved GWh |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Holistic Transition | 2030 | 76.6 | 53.2 | 35.1 | 35.7 | 26.1 | 38.9 | 8.7 | 12.4 | 2.5 | 12.2 |
| Holistic Transition | 2035 | 75.5 | 67.6 | 46.1 | 27.6 | 52.8 | 108.8 | 34.9 | 41.0 | 9.25 | 6.8 |
| Electric Engagement | 2030 | 69.8 | 56.6 | 34.6 | 37.0 | 29.8 | 40.1 | 11.6 | 12.2 | 0 | 9.7 |
| Electric Engagement | 2035 | 73.6 | 54.7 | 57.7 | 41.3 | 48.9 | 89.1 | 15.0 | 27.4 | 8.25 | 13.1 |
| Hydrogen Evolution | 2030 | 64.0 | 42.4 | 35.1 | 40.1 | 26.0 | 36.2 | 7.6 | 9.2 | 0 | 0 |
| Hydrogen Evolution | 2035 | 72.6 | 55.8 | 49.7 | 31.3 | 42.8 | 93.5 | 19.6 | 34.2 | 6.25 | 12.1 |
| Falling Behind | 2030 | 70.4 | 33.4 | 39.2 | 29.5 | 22.8 | 35.4 | 1.8 | 2.3 | 0 | 0 |
| Falling Behind | 2035 | 54.7 | 42.0 | 31.7 | 21.2 | 34.3 | 61.8 | 18.7 | 18.0 | 0 | 0 |
| Ten Year Forecast | 2030 | 64.5 | 37.0 | 35.4 | 22.9 | 25.7 | 46.8 | 6.2 | 7.4 | 0 | 0 |
| Ten Year Forecast | 2035 | 56.0 | 35.2 | 42.9 | 21.2 | 43.7 | 93.1 | 18.3 | 23.7 | 0 | 0 |
| Ten Year Outlook | 2030 | 71.7 | 30.5 | 41.1 | 42.1 | 21.4 | 34.0 | 1.6 | 7.4 | 0 | 0 |
| Ten Year Outlook | 2035 | 85.0 | 52.1 | 43.9 | 35.3 | 40.6 | 69.3 | 15.3 | 49.8 | 0.25 | 7.9 |

Settings since v6.0: links at each link's availability fitted from its flows, unit
commitment (marginal price), the daily gas price of the weather year, and a secure system.
For comparison, the model's own 2025 with the same settings has a mean of £83.0/MWh and a
spread of £51.0/MWh (actual £80.7 and £67.5).

Imports in 2030 are within 7% of FES's in three pathways, 12% below in Hydrogen
Evolution, and 33% and 55% above in Falling Behind and the Ten Year Forecast; in 2035 they
are 1.2 to 2.0 times FES's. Exports are 46% to 74% of FES's in every case: FES expects GB
to export much more in windy hours than links that behave as they did in 2019–2025 do.
Curtailment is 22% to 104% of FES's.

### A secure system first

As FES's fleets stand, several pathways cannot meet demand through 2025's cold, still
spell in January. GB buys capacity through the Capacity Market to a reliability standard
of 3 hours' loss of load expectation a year (DESNZ), so since v6.0 a FES system is made
secure first (`fes.adequacy: secure`, the default): the least firm peaking capacity, in
250 MW steps and costed as gas peaking plant, is added until hours with unserved energy
are within `fes.lole_hours` (3). That is the "Firm added" column: 2.5 GW in Holistic
Transition 2030; 6.25 to 9.25 GW in Holistic Transition, Electric Engagement and Hydrogen
Evolution 2035; 0.25 GW in the Ten Year Outlook 2035; none elsewhere. A single weather year
is one draw, not an expectation; the saturation study below averages two.

`fes.adequacy: as_modelled` keeps the fleet as FES gives it, as before v6.0. Then six
cases leave demand unserved, and the price sits at the £6,000/MWh value of lost load for
much of it. Mean £/MWh and unserved GWh (hours with unserved energy), as modelled:

| Pathway and year | Links as fitted (default) | `availability: gap` | Every link at full capacity |
|---|---:|---:|---:|
| Holistic Transition 2030 | 85.0, 68.0 (16) | 80.2, 47.0 (14) | 66.2, 0 |
| Holistic Transition 2035 | 210.5, 715.2 (81) | 161.6, 508.0 (60) | 84.9, 50.5 (8) |
| Electric Engagement 2030 | 69.8, 9.7 (2) | 60.1, 0 | 63.4, 0 |
| Electric Engagement 2035 | 186.9, 683.2 (81) | 150.5, 480.4 (60) | 77.6, 10.9 (3) |
| Hydrogen Evolution 2035 | 119.9, 214.8 (30) | 93.9, 150.1 (22) | 64.1, 0 |
| Ten Year Outlook 2035 | 85.6, 17.1 (5) | 58.5, 0 | 62.0, 0 |

The cause is link availability. The fitted availability holds on GB's tightest days in
the record: on the 1% of days with the highest GB price in 2019–2025, links imported 3%
(ElecLink) to 42% (Nemo Link, BritNed) of their capacity, below their fitted shares for
every link but East West (39% against 38%), because neighbours were often short at the
same time. So derating links at stress is supported by the flows. What the model leaves
out is what FES counts on in those hours: demand response, new flexibility and neighbours'
own 2030s fleets. The secure top-up stands in for all of that with the cheapest firm
capacity, so read it as "this much firm capacity, or its equivalent", not as a forecast of
new gas plant.

### A battery on pathway prices

The same 1 MW / 2 MWh battery (95% each way, £5/MWh wear) on 358 days of each modelled
year (the first week has no last week to plan on), from the app's precomputed results
(`data/app/`), GBP per MW-year:

| Prices | Last week's prices | Perfect foresight |
|---|---:|---:|
| Actual 2025 | 36,208 | 44,974 |
| Model 2025, links + commitment | 11,293 | 26,038 |
| Holistic Transition 2030 / 2035 | 3,448 / 8,440 | 19,657 / 25,450 |
| Electric Engagement 2030 / 2035 | 4,025 / 11,010 | 26,685 / 20,663 |
| Hydrogen Evolution 2030 / 2035 | 5,860 / 5,145 | 17,514 / 22,031 |
| Falling Behind 2030 / 2035 | 3,646 / 4,098 | 11,514 / 15,822 |
| Ten Year Forecast 2030 / 2035 | 3,157 / 3,078 | 12,940 / 12,421 |
| Ten Year Outlook 2030 / 2035 | 2,166 / 3,937 | 9,288 / 19,400 |

Compare pathways with the model's own 2025, not with actual 2025: on modelled 2025 prices
the battery's perfect-foresight value is 58% of its actual value, and the model's daily
spread is 76% of the real one. Against that baseline, every pathway's perfect-foresight
value is about the same or lower: 2% lower in Holistic Transition 2035 and 2% higher in
Electric Engagement 2030, 15% to 33% lower in Holistic Transition 2030, Electric
Engagement and Hydrogen Evolution 2035, Hydrogen Evolution 2030 and the Ten Year Outlook
2035, and 39% to 64% lower in Falling Behind, the Ten Year Forecast and the Ten Year
Outlook 2030. With secure systems the 2035 pathways no longer rise far above the baseline
on days of lost load (before v6.0 they reached 1.8 to 2.7 times it), but scarcity still
matters: with perfect foresight over the full year, the one or two days with an hour at
£1,000/MWh or more earn 29% to 49% of the value in the six cases that have them (49% of
Holistic Transition 2035's). Planning on last week's prices keeps 15% to 53% of the
perfect-foresight value, against 81% on actual 2025 prices and 43% on the model's own
2025.

## How much storage can GB use?

The batteries above join a fleet that FES has already sized: 23 to 33 GW of batteries in
2035 in FES 2025's pathways, storing 1.3 to 1.5 hours on average. What happens to the
value of one more battery as that fleet grows, once the system is secure? `openenergy system saturation` scales each pathway's
2035 battery fleet from none to three times FES's figure (same duration), and for each fleet
adds the least firm capacity that keeps loss of load, averaged over the 2024 and 2025
weather years, within the 3-hour standard. A 1 MW / 2 MWh battery (95% each way, £5/MWh
wear) is then valued with perfect foresight on each year's modelled prices
(`data/scenarios/saturation.csv`; try it in the [web app](https://open-energy-eight.vercel.app/2035)).
FES 2025 publishes figures from 2024, so these two weather years are all a FES system can
be scaled from today; the Ten Year Outlook, which has no 2024 wind, is left out.

The pathways with no shortfall once they have batteries first (Ten Year Forecast needs
0.75 GW of firm capacity with no batteries, none with half its fleet). GBP per MW-year,
mean of the two weather years:

| Battery fleet (× FES 2035) | 0 | 0.5 | 1 | 2 | 3 |
|---|---:|---:|---:|---:|---:|
| Falling Behind: fleet GW | 0 | 11.3 | 22.7 | 45.3 | 68.0 |
| Falling Behind: one more battery earns | 43,609 | 21,840 | 15,551 | 10,362 | 8,017 |
| Falling Behind: daily spread (£/MWh) | 72.2 | 47.9 | 40.6 | 32.6 | 28.2 |
| Ten Year Forecast: fleet GW | 0 | 15.0 | 29.9 | 59.9 | 89.8 |
| Ten Year Forecast: one more battery earns | 40,897 | 17,196 | 12,057 | 8,130 | 6,296 |
| Ten Year Forecast: daily spread (£/MWh) | 71.9 | 41.0 | 34.3 | 28.1 | 24.3 |

The first half of the FES fleet takes half or more of a battery's value away; the next two
and a half fleets take nearly two thirds of what is left. Batteries earn by flattening the
daily spread, so each one leaves less spread for the next. The two weather years agree: in
Falling Behind a battery joining the FES fleet earns £14,927 on 2024's weather and
£16,176 on 2025's.

The other three pathways are short of firm capacity in a cold, still spell, and the
batteries do little about it:

| Pathway | Firm capacity added (GW) for a fleet of × 0 / 0.5 / 1 / 2 / 3 | Firm capacity each MW of the FES fleet replaces (MW) |
|---|---:|---:|
| Holistic Transition | 11.25 / 9.25 / 8.25 / 8.0 / 8.25 | 0.10 |
| Electric Engagement | 11.25 / 8.75 / 8.25 / 7.25 / 7.25 | 0.09 |
| Hydrogen Evolution | 8.75 / 6.75 / 4.75 / 4.0 / 3.0 | 0.16 |

The FES fleets store under an hour and a half on average, and the shortfalls they would
cover last longer: the first half of the fleet saves 2.0 to 2.5 GW of firm capacity, and
the next two and a half fleets 1.0 to 3.75 GW more. In 250 MW steps the search is not
perfectly monotonic (Holistic Transition needs 8.0 GW at twice the fleet and 8.25 GW at
three times). In these pathways a battery's value also rests on a handful of scarcity
days: a 1 MW battery with the FES fleet earns £16,591 in Holistic Transition, £17,441 in
Electric Engagement and £26,961 in Hydrogen Evolution, of which 23%, 17% and 45% comes on
the days with an hour priced at £1,000/MWh or more (one to three across the two weather
years). Holistic Transition's and Electric Engagement's are all in 2025's weather; a value
resting on them is a statement about one cold week, not about the pathway.

What this says, with its limits: in a GB system that has enough firm capacity, battery
value halves or more as the first 11 to 15 GW of FES's fleet arrives, and falls to 15–18% of the
first battery's value at three times the fleet. It is the perfect-foresight value of a
2-hour battery on a model whose daily spread is 76% of the real one in 2025, so the levels
are lower bounds on what the spread allows and upper bounds on what a forecast captures;
the shape of the curve is the result.

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
