# Command line

Install with `uv sync` (add `--extra forecast` for the gradient-boosting forecaster), then
prefix commands with `uv run`.

## `openenergy run`

```bash
uv run openenergy run examples/gb-2019-naive.yaml [--out DIR]
```

Runs one scenario, prints a summary and writes [outputs](scenarios.md#outputs).

```text
gb-2019-naive (naive_last_week, GBP)
  days simulated        363 (2 skipped)
  revenue               13,919.64 GBP
  revenue per MW-year   13,996.34 GBP
  captured spread       15.79 GBP/MWh
  equivalent cycles     464.7
  final SOH             0.9807
  forecast MAE / RMSE   6.01 / 8.12 GBP/MWh
  capture ratio         73.0%
  outputs               outputs/gb-2019-naive
```

The two skipped days are 7–8 June 2019, when the source data has a day-long gap.

A scenario with [`assets`](scenarios.md#assets-co-located-sites) also reports the plant
and the co-location comparison:

```text
gb-2019-pv-colocated (naive_last_week, GBP)
  days simulated        361 (2 skipped)
  revenue               614,536.53 GBP
  premium               0.00 GBP
  plant output          13,265 MWh (0.3% curtailed)
  equivalent cycles     462.5
  final SOH             1.0000
  forecast MAE / RMSE   6.02 / 8.14 GBP/MWh
  capture ratio         96.2%
  plant captured price  41.24 GBP/MWh (96.1% of baseload)
  separate assets       616,899.61 GBP (plant 546,977 + battery 69,922)
  co-location value     -2,363.08 GBP (upper bound: plant output known)
```

## `openenergy report`

```bash
uv run openenergy report DIR [DIR ...] [-o report.html] [--title TEXT] [--cdn]
```

Writes one HTML file of charts and tables from directories written by `run`, `system run`
or `system validate --out`, or from a `sweep --out` CSV. Needs the `report` extra
(`uv sync --extra report`). See [Reports](reports.md).

## `openenergy capture`

```bash
uv run openenergy capture data/time_series/time_series_60min_singleindex_filtered.csv -t solar
```

Captured price and capture rate per year for each renewable technology (all by default,
or repeat `-t`), with capacity factor and the share of output at negative prices.

```text
year  technology           CF   baseload   captured  capture  neg-price   (prices in GBP/MWh)
2015  solar             18.2%      40.24      42.63   105.9%      0.00%
2016  solar             15.3%      40.47      38.13    94.2%      0.00%
2017  solar             14.4%      45.33      42.52    93.8%      0.00%
2018  solar             15.6%      57.44      56.46    98.3%      0.00%
2019  solar             15.3%      42.89      41.22    96.1%      0.00%
```

## `openenergy compare`

```bash
uv run openenergy compare examples/gb-2019-{naive,ml,perfect}.yaml
```

Runs several scenarios and ranks them by revenue (plus any premium), with revenue per
MW-year (battery-only scenarios), capture ratio and cycles.

## `openenergy netload`

```bash
uv run openenergy netload data/time_series/time_series_60min_singleindex_filtered.csv \
  [--scale-wind 3] [--scale-solar 3] [--must-run 8000]
```

Net load per year: renewable share, mean, peak and minimum, 99th-percentile 1-hour and
3-hour ramps, surplus above the must-run floor and, for the actual system, the price slope
per GW of net load. See [System analysis](system.md).

## `openenergy storage`

```bash
uv run openenergy storage DATA --scale-wind 3 --scale-solar 3 --must-run 8000 \
  --power 2000,5000,10000 --hours 4,8,24
```

Share of surplus absorbed by storage fleets of each power (MW) and duration (hours).

## `openenergy sweep`

```bash
uv run openenergy sweep examples/gb-2019-naive.yaml \
  --set battery.energy_mwh=1,2,4 --set dispatch.degradation_cost=0,5 [--out sweep.csv]
```

Runs a scenario for every combination of `--set dotted.key=v1,v2` values (up to 100) and
ranks them by total revenue. For a [system scenario](system-model.md) it keeps the order
given and reports price, emissions, curtailment, cost and any battery's revenue.

## `openenergy system validate`

```bash
uv run openenergy system validate [--start 2015-04-01] [--end 2020-09-30] [--out backcast/]
uv run openenergy system validate --start 2021-01-01 --end 2025-12-31
uv run openenergy system validate --commitment --price start
```

Rebuilds GB prices and gas and coal output from fuel, carbon and fleet data, and compares
each year with what happened: mean, MAE, correlation, 95th percentile and average daily
spread of price, gas and coal output, and CO2. The system data runs to the end of 2025.
Actual prices come from the bundled OPSD file and, after it ends in September 2020, the
Ember file; `--prices` (repeatable, earlier files first) points at other copies.
`--commitment` adds start-up costs and minimum stable output
([unit commitment](system-model.md#unit-commitment); about a minute per year). `--price
start` compares the start price instead of the marginal price and needs `--commitment`.
`--data` points at another copy of `data/system`. `--out` writes `backcast.csv`,
`hourly.csv` and `summary.json`.

## `openenergy system run`

```bash
uv run openenergy system run examples/gb-2019-system.yaml [--out outputs/gb-2019-system]
```

Dispatches one GB year with a scenario's changes and prints price, generation by
technology, curtailment, emissions, system cost and, if the scenario has a battery, its
revenue on the modelled prices. Writes `dispatch.csv` and `summary.json`. Scenarios with
storage need the `system` extra (`uv sync --extra system`).

## `openenergy system zones`

```bash
uv run --extra system openenergy system zones [--start 2023-01-01] [--end 2025-12-31] [--limit scotex] [--out zones/]
```

Splits each year's system into Scotland and England and Wales
([two-zone model](constraints.md#a-two-zone-model)) and compares the modelled transfer
across the boundary with NESO's recorded one: mean, correlation and hours at the limit, how
often the zones' prices split, and a 1 MW / 2 MWh battery's perfect-foresight revenue on
each zone's price. `--limit` is `scotex` (NESO's monthly day-ahead limit, from 2023),
`recorded` (the year's largest recorded transfer) or a number of MW. `--out` writes
`two_zones_by_year.csv` and `two_zones_hourly.csv`.

## `openenergy invest`

```bash
uv run openenergy invest [--cost-year 2025] [--cost-scale 1] [--life 15] [--rate 0.07] [--cm-price GBP/kW] [--out cases.csv]
```

Values a 1 MW / 2 MWh battery over its life on each revenue case
([Investment case](investment.md)): yearly net cash flow, break-even build cost, net
present value and internal rate of return. Costs are NREL's ATB (US, converted to pounds;
`--cost-scale` scales them) and the Capacity Market pays the latest four-year-ahead price
unless `--cm-price` is given.

## `openenergy data info`

```bash
uv run openenergy data info data/time_series/time_series_60min_singleindex_filtered.csv
```

Lists each price zone with its currency, date range and number of complete days.

## `openenergy data update`

```bash
uv run openenergy data update [--dir DIR]
```

Downloads the latest GB hourly day-ahead prices from Ember (CC BY 4.0, in EUR as
published) and the ECB's daily GBP rates into `DIR` (default
`~/.cache/openenergy/prices`, or `$XDG_CACHE_HOME/openenergy/prices`). Point a scenario at
the result with `data: {source: ember, path: DIR/gb_day_ahead_ember.csv}`. The bundled copy
in `data/prices/` is refreshed by `scripts/fetch_prices.py`. `--fundamentals` also
downloads the daily gas price and NESO's and Elexon's day-ahead demand and wind forecasts
(to `fundamentals/` beside `DIR`).

## `openenergy forecast live`

```bash
uv run openenergy data update --fundamentals
uv run --extra forecast openenergy forecast live [--out live/] [--day YYYY-MM-DD] [--replace]
```

Forecasts tomorrow's GB day-ahead prices (or `--day`'s, which must not have started) from
the cached data, with the [fundamentals forecast](research.md#live-forecast), and the plan
of a 1 MW / 2 MWh battery on it. Adds the forecast to `forecasts.csv` in `--out` (a rerun
for the same day keeps the first forecast, so the record shows what was known then;
`--replace` forecasts it again), catches up any day of the last week since the record began
that has no forecast (with what was known by noon the day before; marked `catch_up`),
scores every forecast whose day has published prices, and writes `live.json` for the web
app: the last 14 scored days, and summaries over the last 30 and since the start that
leave caught-up days out. It stops with an error if tomorrow's
demand or wind forecast is not out yet (NESO's usually is by 09:00 UTC).

## Errors

Invalid scenarios, missing files and infeasible plans print a single `error:` line and
exit with status 1.
