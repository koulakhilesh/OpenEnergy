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
uv run openenergy compare examples/*.yaml
```

Runs several scenarios and ranks them by revenue (plus any premium), with revenue per
MW-year (battery-only scenarios), capture ratio and cycles.

## `openenergy data info`

```bash
uv run openenergy data info data/time_series/time_series_60min_singleindex_filtered.csv
```

Lists each price zone with its currency, date range and number of complete days.

## Errors

Invalid scenarios, missing files and infeasible plans print a single `error:` line and
exit with status 1.
