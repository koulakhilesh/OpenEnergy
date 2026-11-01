# OpenEnergy

OpenEnergy backtests battery storage and renewable plants against real day-ahead power
prices. You describe the assets and a forecasting approach in a short YAML file;
OpenEnergy plans each day on the forecast, settles the plan at the prices that actually
cleared, and tells you what the site earned, how hard the battery worked, and how close it
came to a perfect-foresight benchmark.

It is built for research questions such as:

- How much is a 2-hour battery worth in the GB day-ahead market?
- How much more does it earn selling frequency response too?
- How much revenue does a better price forecast buy?
- How much of the average price do solar and wind actually capture?
- Can a battery share a solar farm's grid connection without losing money?
- As wind and solar grow, how much surplus appears, and how much storage absorbs it?
- What do storage and renewables do to emissions, and what does a carbon price change?
- How well does a cost-based model of GB plants reproduce real prices, and what changes
  with more wind, more storage or a different carbon price?
- What might GB prices and a battery look like on NESO's Future Energy Scenarios, with
  interconnectors trading at neighbouring markets' prices?

## Quick start

```bash
git clone https://github.com/koulakhilesh/OpenEnergy.git
cd OpenEnergy
uv sync --extra forecast
uv run openenergy compare examples/gb-2019-{naive,ml,perfect}.yaml
```

```text
scenario         forecast             days       revenue   per MW-yr   capture   cycles
gb-2019-perfect  perfect_foresight     363        19,075      19,180    100.0%      464
gb-2019-ml       gradient_boosting     363        14,086      14,164     73.8%      400
gb-2019-naive    naive_last_week       363        13,920      13,996     73.0%      465
```

A 1 MW / 2 MWh battery trading GB day-ahead prices in 2019 would have earned about
£14k per MW-year planning on last week's prices, or 73% of what perfect foresight allows.

The same battery on every year of the bundled prices (`examples/gb-2022-naive.yaml` with
other dates, and with `forecast: {method: fundamentals, path: ...}`; Ember prices, GBP per
MW-year):

| Year | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Last week's prices | 20,633 | 18,887 | 13,943 | 17,144 | 74,169 | 76,948 | 35,957 | 28,690 | 35,861 |
| OpenEnergy forecast | | | 15,148 | 18,382 | 70,771 | 80,150 | 39,415 | 33,410 | 39,361 |
| Perfect foresight | 26,252 | 25,380 | 19,538 | 22,362 | 89,282 | 102,550 | 45,968 | 38,870 | 44,564 |
| Capture, last week's prices | 79% | 74% | 71% | 77% | 83% | 75% | 78% | 74% | 80% |
| Capture, OpenEnergy forecast | | | 78% | 82% | 79% | 78% | 86% | 86% | 88% |

Revenue followed the gas crisis: over five times the 2019 level in 2021–2022, and 2.1 to
2.6 times it in 2023–2025. Last week's prices kept 71–83% of the
perfect-foresight value every year; OpenEnergy's forecast (NESO's demand forecast,
Elexon's wind forecast, the daily gas price and recent prices, as known the day before)
kept 78–88% and did better every year except 2021, when gas prices rose faster than a
model trained on calmer years could follow (see [Research](guides/research.md)).

Renewables are one command away:

```bash
uv run openenergy capture data/time_series/time_series_60min_singleindex_filtered.csv -t solar
```

GB solar captured 94–106% of the average day-ahead price each year from 2015 to 2019, and
adding a 5 MW battery behind an existing 10 MW solar connection cost almost nothing in
lost trading (see [Research](guides/research.md)).

The whole system is one command too:

```bash
uv run openenergy netload data/time_series/time_series_60min_singleindex_filtered.csv \
  --scale-wind 3 --scale-solar 3 --must-run 8000
```

Tripling 2019 wind and solar would leave 14 TWh of surplus above an 8 GW must-run floor;
a 10 GW / 24 h storage fleet absorbs about three-quarters of it
(see [System analysis](guides/system.md)).

And the plants behind the price:

```bash
uv run openenergy system validate
```

Rebuilt from fuel, carbon and fleet data alone, GB's 2019 average price comes out at
£38.1/MWh against £42.9 actual, with a correlation of 0.69, but its peaks are far too low:
a battery that earned £16k per MW-year on real 2019 prices earns almost nothing on the
modelled ones. With the daily gas price (v6.0), the model follows the 2022 gas crisis with
a correlation of 0.81 (0.40 with quarterly prices) (see [System model](guides/system-model.md)).

## What it does

1. **Loads prices, capacity factors, demand and carbon intensity** from the bundled
   [Open Power System Data, Ember and NESO](data.md) extracts (GB prices to October 2026)
   and checks them: UTC timestamps, a regular grid, reported gaps and filtered telemetry
   glitches.
2. **Forecasts** each day using only data available at the decision time (noon the day
   before by default), from last week's prices to OpenEnergy's forecast built on NESO's
   demand and Elexon's wind forecasts and the daily gas price.
3. **Plans** the day with a mixed-integer optimisation that respects power and energy
   limits, efficiencies, an end-of-day state of charge and, for co-located sites, a shared
   grid connection; an optional carbon price steers dispatch.
4. **Settles** the plan at actual prices through the battery physics, including cycle and
   calendar ageing.
5. **Reports** revenue, cycles, state of health, forecast error, the capture ratio against
   perfect foresight, net emissions and, for sites, curtailment, the plant's captured
   price and the value of co-location against separate connections.
6. **Analyses the system**: net load, ramps and surplus as renewables scale, and the
   storage needed to absorb that surplus; `openenergy sweep` sizes storage for a site.
7. **Models GB dispatch**: CCGT, coal and peaking plant in merit order from DUKES fleet
   data, fuel and carbon prices, checked against 2015–2025, with scenarios for renewables,
   storage, fleet and carbon policy (storage via the optional PyPSA backend), and optional
   unit commitment with start-up costs and minimum stable output.
8. **Reports** any saved run, system scenario, backcast or sweep as one interactive HTML
   page of charts and tables (`openenergy report`; see the
   [example](reports/example.html)).
9. **Stacks revenue**: GB Dynamic Containment, Moderation and Regulation co-optimised with
   day-ahead trading in the same plan, with the energy each service moves taken from GB
   frequency data (see [Revenue stacking](guides/revenue-stacking.md)).
10. **Looks forward**: NESO Future Energy Scenarios pathways to 2035 on a historic weather
    year, made secure to GB's reliability standard, with GB's interconnectors as
    price-taking links to six neighbouring markets at availabilities fitted from their
    actual flows, and unit commitment; and how much storage GB can use before a battery
    stops paying (see [Forward scenarios](guides/forward-scenarios.md)).
11. **Runs in the browser**: a [web app](guides/web-app.md) simulates Britain's grid hour
    by hour from 2019, with a battery trading on a plan the optimiser makes in your
    browser, lets you play a day against it, and values a battery on any GB year from 2017
    or on a FES pathway; try it at
    [open-energy-eight.vercel.app](https://open-energy-eight.vercel.app/).
12. **Checks itself against real batteries**: every GB grid battery's metered output and
    Balancing Mechanism cashflows from Elexon since 2021, next to what the optimiser does,
    north and south of the Scottish border (see [Real batteries](guides/real-batteries.md)).

See [Concepts](concepts.md) for the equations and [Scenarios](guides/scenarios.md) for
every setting.

## Roadmap

**Released**

| Release | Scope |
|---------|-------|
| v2.0 | Battery arbitrage backtesting: physics, ageing, dispatch, forecasters, CLI |
| v2.1 | PV and wind assets, captured price, co-located storage |
| v2.2 | Net load, surplus, storage sizing, emissions |
| v3.0 | GB system dispatch with conventional generation via PyPSA, checked against 2015–2020 |
| v3.1 | Optional unit commitment (start-up costs, minimum stable output) and a start-cost price, re-checked against 2015–2020 without fitting to prices |
| v3.2 | Data to 2025: GB prices from Ember, NESO generation and carbon intensity, DUKES and fuel prices, UK ETS; `openenergy data update`; backcast of the gas crisis and coal exit |
| v3.3 | Multi-day planning horizon (`dispatch.lookahead_days`), and a measured answer on planning under price uncertainty: for day-ahead-only trading a scenario plan equals one forecast, and risk aversion costs revenue |
| v3.4 | Reports: `openenergy report` turns saved runs, system scenarios, backcasts and sweeps into one interactive HTML file; chart functions reusable from Python |
| v3.5 | Revenue stacking: GB Dynamic Containment, Moderation and Regulation co-optimised with day-ahead trading; a measured answer on balancing (imbalance prices are valuable only with a forecast open data does not give; revised in v6.0) and on stochastic planning (still no value) |
| v4.0 | Forward scenarios from NESO's Future Energy Scenarios on a historic weather year; GB's interconnectors as price-taking links to six neighbouring markets, checked against actual flows 2019–2025; a web app (FastAPI, Vercel) valuing a battery on history or a FES pathway |
| v4.1 | A usable [web app](https://open-energy-eight.vercel.app/): the answer first in plain words, instant results for common batteries, value by year and by FES pathway at a glance, side-by-side comparison with shareable links, explanations next to each term, CSV and scenario downloads, and a JSON API; `CITATION.cff` and PyPI release |
| v4.2 | A more credible model: unit commitment with interconnector links; each link's availability fitted from its actual flows, never from prices; a measured answer on the missing daily spread (the everyday intraday shape, not negative prices); forward scenarios and the app re-run. GB zones were dropped: GB keeps one national wholesale price ([DESNZ, REMA summer update, July 2025](https://www.gov.uk/government/publications/review-of-electricity-market-arrangements-rema-summer-update-2025)) |
| v5.0 | A React and TypeScript front end on an extended JSON API (options, explore, compare, FES table), typed from the OpenAPI schema and tested end to end; interconnector availability by price gap from hourly flows, tested out of sample (an option: it does not beat the flat share); data refreshed to October 2026; versioned docs and a Zenodo DOI |
| v6.0 | The daily gas price in the system model; a day-ahead forecast from NESO's demand and Elexon's wind forecasts, the gas price and auction prices (`forecast: fundamentals`); FES systems made secure to the reliability standard and a storage saturation study (`openenergy system saturation`); the battery optimiser in the browser (Battery Lab, Grid replay, 2035, Beat the battery); a Gymnasium environment; constraint evidence; an end-of-day energy target that is now exact ([What's new](whats-new.md#60)) |
| v6.1 | The web app as a simulator: Britain's grid hour by hour with power flowing in by fuel and a battery trading on the in-browser optimiser, play controls, keys and a year strip; Play, 2035 and Research tabs; revenue after wear in the browser, so perfect foresight is a true ceiling; NESO's generation mix to October 2026 ([What's new](whats-new.md#61-the-web-app-becomes-a-simulator)) |
| v7.0 | Real batteries: every GB grid battery's physical notifications, metered output and Balancing Mechanism volumes and cashflows from Elexon (2021 to October 2026), compared with the optimiser and by zone; Scotland and England & Wales demand, transfer and capacity by year; a Real batteries tab in the web app; the docs' headline numbers checked against their sources on every test run ([What's new](whats-new.md); current) |

**Planned**

| Release | Scope |
|---------|-------|
| v7.1 | A two-zone dispatch model (Scotland and England & Wales) checked against the observed transfer, to value where a battery relieves constraints; the saturation study on every weather year from 2019, using capacity by year; the evening peak premium the cost-based model misses |

Alongside releases: refresh and re-check the bundled data
every release; keep CI and its actions current; revisit stochastic planning if an open,
forecastable market price appears. Ideas are welcome in
[issues](https://github.com/koulakhilesh/OpenEnergy/issues).
