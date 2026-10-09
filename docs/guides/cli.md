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

## `openenergy compare`

```bash
uv run openenergy compare examples/*.yaml
```

Runs several scenarios and ranks them by revenue, with revenue per MW-year, capture ratio
and cycles.

## `openenergy data info`

```bash
uv run openenergy data info data/time_series/time_series_60min_singleindex_filtered.csv
```

Lists each price zone with its currency, date range and number of complete days.

## Errors

Invalid scenarios, missing files and infeasible plans print a single `error:` line and
exit with status 1.
