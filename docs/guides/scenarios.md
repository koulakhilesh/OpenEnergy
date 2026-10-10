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

## `assets` (co-located sites)

Optional. Adds renewable plants that share the battery's grid connection.

```yaml
assets:
  pv: {capacity_mw: 10, degradation_per_year: 0.005}
  wind: {capacity_mw: 5, technology: wind_offshore}
grid:
  export_limit_mw: 12
```

| Key | Default | Meaning |
|-----|---------|---------|
| `pv`, `wind` | none | At least one plant |
| `capacity_mw` | required | Installed capacity |
| `degradation_per_year` | `0` | Fraction of output lost per year, compounding |
| `technology` | `solar` / `wind` | OPSD profile: `solar`, `wind`, `wind_onshore`, `wind_offshore` |

OPSD capacity factors end on 29 December 2019, so site scenarios must end by then.

## `grid`

Only valid with `assets`.

| Key | Default | Meaning |
|-----|---------|---------|
| `export_limit_mw` | total plant capacity | Shared export limit |
| `import_limit_mw` | export limit | Grid charging limit; `0` forbids grid charging |
| `premium_per_mwh` | `0` | Support paid per MWh of renewable output delivered |

## `carbon`

Optional. Reports net emissions and can steer dispatch with a carbon price.

```yaml
carbon:
  path: ../data/carbon_intensity/gb_national.csv
  price_per_t: 50
  planning: last_week
```

| Key | Default | Meaning |
|-----|---------|---------|
| `path` | required | NESO carbon-intensity CSV; relative to the scenario file |
| `price_per_t` | `0` | Carbon price in currency per tCO2 added to planning prices |
| `planning` | `last_week` | Intensity dispatch plans on: `last_week` (no lookahead) or `actual` (upper bound) |

Carbon intensity covers 2018 to September 2020. Days without complete intensity are
skipped.

## System scenarios

A file with a `system:` section instead of `data:` describes one GB year for the
[system model](system-model.md): scaled renewables and fixed profiles, thermal capacity,
fuel and carbon prices, added storage, and optionally a `battery` valued on the modelled
prices. Run it with `openenergy system run`; the full reference is on that page.

## Outputs

`openenergy run` writes to `outputs/<name>/` unless `--out` is given:

- `intervals.csv`: price, forecast, charge, discharge, stored energy and revenue per
  interval; sites add available output, plant to grid, plant to battery, curtailment,
  grid charging, net export and premium;
- `daily.csv`: revenue, expected revenue, energy charged and discharged, cycles, SOH and
  end-of-day energy; sites add premium, available and curtailed energy;
- `summary.json`: the headline metrics, skipped days with reasons, the number of
  interpolated intervals, the full validated configuration, the package version and the
  data attribution; sites add the co-location comparison, the plant's capture metrics,
  the number of clipped capacity factors and the upper-bound note; carbon runs add
  `emissions_t`, the NESO attribution, rejected intensity values and the
  average-intensity caveat.
