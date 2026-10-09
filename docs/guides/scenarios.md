# Scenarios

A scenario is a YAML file describing the data, the battery, the forecast and the dispatch
settings. Unknown keys and invalid values are rejected with the setting named.

```yaml
name: gb-2019-naive            # letters, digits, ".", "_", "-"; used as the output folder
data:
  path: ../data/time_series/time_series_60min_singleindex_filtered.csv
  zone: GB_GBN
  start: 2019-01-01
  end: 2019-12-31
battery:
  power_mw: 1
  energy_mwh: 2
  eta_charge: 0.95
  eta_discharge: 0.95
  cycle_fade: 0.00002
  calendar_fade: 0.01
forecast: naive_last_week
dispatch:
  degradation_cost: 5
```

## `data`

| Key | Default | Meaning |
|-----|---------|---------|
| `path` | required | OPSD time-series CSV; relative paths resolve against the scenario file |
| `zone` | `GB_GBN` | Bidding zone (see `openenergy data info`) |
| `start`, `end` | whole file | First and last UTC day to simulate, inclusive |
| `max_gap_hours` | `2` | Interior price gaps up to this length are linearly interpolated |

When `start` is set, the 14 days before it are loaded as forecaster history only.

## `battery`

| Key | Default | Meaning |
|-----|---------|---------|
| `power_mw` | required | Charge and discharge power rating |
| `energy_mwh` | required | Rated energy capacity |
| `eta_charge`, `eta_discharge` | `0.95` | One-way efficiencies in (0, 1] |
| `soc_min`, `soc_max` | `0`, `1` | State-of-charge window, as fractions of usable energy |
| `initial_soc` | `0.5` | Starting state of charge |
| `cycle_fade` | `0` | Fraction of capacity lost per equivalent full cycle |
| `calendar_fade` | `0` | Fraction of capacity lost per year |

## `forecast`

Either a method name, or a mapping with `method` and its options.

| Method | Options |
|--------|---------|
| `naive_last_week` (default) | none |
| `perfect_foresight` | none |
| `noisy_foresight` | `error_std` (required, currency/MWh), `seed` |
| `gradient_boosting` | `train_start`, `train_end` (required, before `data.start`), `seed` |

## `dispatch`

| Key | Default | Meaning |
|-----|---------|---------|
| `end_soc` | start energy | End-of-day state of charge, as a fraction of usable energy |
| `degradation_cost` | `0` | Cost per MWh of throughput, in the price currency |
| `max_cycles` | none | Cap on equivalent full cycles per day |
| `mip_rel_gap` | `1e-6` | Solver optimality tolerance |

## Other keys

| Key | Default | Meaning |
|-----|---------|---------|
| `lead_hours` | `12` | Hours before each UTC day that the plan is fixed |

## Outputs

`openenergy run` writes to `outputs/<name>/` unless `--out` is given:

- `intervals.csv`: price, forecast, charge, discharge, stored energy and revenue per interval;
- `daily.csv`: revenue, expected revenue, energy charged and discharged, cycles, SOH and
  end-of-day energy;
- `summary.json`: the headline metrics, skipped days with reasons, the number of
  interpolated intervals, the full validated configuration, the package version and the
  data attribution.
