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
  revenue               13,918.48 GBP
  revenue per MW-year   13,995.16 GBP
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
  revenue               614,474.47 GBP
  premium               0.00 GBP
  plant output          13,265 MWh (0.3% curtailed)
  equivalent cycles     462.5
  final SOH             1.0000
  forecast MAE / RMSE   6.02 / 8.14 GBP/MWh
  capture ratio         96.2%
  plant captured price  41.24 GBP/MWh (96.1% of baseload)
  separate assets       616,873.99 GBP (plant 546,977 + battery 69,897)
  co-location value     -2,399.52 GBP (upper bound: plant output known)
```

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
```

Rebuilds GB prices and gas and coal output from fuel, carbon and fleet data, and compares
each year with what happened. `--data` and `--prices` point at other copies of
`data/system` and the OPSD file. `--out` writes `backcast.csv`, `hourly.csv` and
`summary.json`.

## `openenergy system run`

```bash
uv run openenergy system run examples/gb-2019-system.yaml [--out outputs/gb-2019-system]
```

Dispatches one GB year with a scenario's changes and prints price, generation by
technology, curtailment, emissions, system cost and, if the scenario has a battery, its
revenue on the modelled prices. Writes `dispatch.csv` and `summary.json`. Scenarios with
storage need the `system` extra (`uv sync --extra system`).

## `openenergy data info`

```bash
uv run openenergy data info data/time_series/time_series_60min_singleindex_filtered.csv
```

Lists each price zone with its currency, date range and number of complete days.

## Errors

Invalid scenarios, missing files and infeasible plans print a single `error:` line and
exit with status 1.
