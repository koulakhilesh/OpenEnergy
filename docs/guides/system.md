# System analysis

OpenEnergy can also look at the whole GB system: how wind and solar reshape the demand
left for other plant, when they produce more than the system can use, how much storage that
calls for, and what storage does to emissions.

## Net load

Net load is demand minus wind and solar output. Scaling wind and solar models more
installed capacity with the same weather:

$$N_t = L_t - k_w W_t - k_s S_t$$

```bash
uv run openenergy netload data/time_series/time_series_60min_singleindex_filtered.csv
```

| Year | Renewable share | Min net load (GW) | 1 h ramp, p99 (GW) | Price per GW of net load |
|-----:|----------------:|------------------:|-------------------:|-------------------------:|
| 2015 | 12.0% | 11.3 | 7.3 | £0.80/MWh |
| 2017 | 16.5% | 10.1 | 6.5 | £1.23/MWh |
| 2019 | 18.7% | 6.7 | 7.1 | £1.21/MWh |
| 2020 (to Sep) | 24.0% | 3.1 | 7.1 | £1.13/MWh |

Each extra GW of net load raised the GB day-ahead price by about £1/MWh. Ramps are 99th
percentiles of absolute changes, so a single bad reading cannot set them.

!!! note "Load data quality"
    ENTSO-E's GB actual load has telemetry glitches, such as hours at 511 MW against real
    demand of 15 GW or more. `load_system` removes load readings that deviate from their
    5-hour median by more than 25% of the 99th percentile, or fall below half their 7-day
    median (133 of 50,394 hours), and reports the count. Wind and solar are unchanged.
    The load is total demand, so subtracting solar does not double count it.

## Surplus as renewables grow

**Surplus** is renewable output the system cannot use: how far net load falls below a
must-run floor $F$ of inflexible generation, $U_t = \max(0, F - N_t)$.
[`examples/renewables_scaling.py`](https://github.com/koulakhilesh/OpenEnergy/blob/master/examples/renewables_scaling.py)
scales 2019 wind and solar with an 8 GW floor:

| Scale | Renewable share | Min net load (GW) | 1 h ramp, p99 (GW) | Surplus (TWh) | Share of renewable output |
|------:|----------------:|------------------:|-------------------:|--------------:|--------------------------:|
| ×1 | 18.7% | 6.7 | 7.0 | 0.00 | 0.0% |
| ×2 | 37.4% | −3.8 | 10.0 | 1.61 | 1.5% |
| ×3 | 56.1% | −20.2 | 14.1 | 14.39 | 8.6% |
| ×4 | 74.8% | −36.6 | 18.3 | 43.34 | 19.5% |

Surplus grows much faster than capacity: doubling from ×2 to ×4 multiplies it by 27, and
ramps steepen as renewables set more of the shape of net load.

## Storage to absorb surplus

A storage fleet charges from surplus and releases as soon as net load is back above the
floor, never creating new surplus:

```bash
uv run openenergy storage data/time_series/time_series_60min_singleindex_filtered.csv \
  --scale-wind 3 --scale-solar 3 --must-run 8000 --power 2000,5000,10000 --hours 4,8,24
```

For 2019 with renewables ×3:

| Power | 4 h | 8 h | 24 h |
|------:|----:|----:|-----:|
| 2 GW | 12.6% | 17.5% | 23.1% |
| 5 GW | 25.7% | 35.7% | 48.0% |
| 10 GW | 39.8% | 54.4% | 73.2% |

Returns diminish with both power and duration, and duration matters: much of the surplus
arrives in multi-day windy spells that short-duration storage cannot hold.

## Sizing a site

`openenergy sweep` runs any scenario over a grid of settings:

```bash
uv run openenergy sweep examples/gb-2019-naive.yaml \
  --set battery.energy_mwh=1,2,4 --set dispatch.degradation_cost=0,5,15
```

For a 1 MW battery in GB 2019 without a degradation cost, revenue per MW-year rises from
£8.5k (1 h) to £15.8k (2 h) and £24.3k (4 h), so each extra hour earns less. A
£15/MWh degradation cost exceeds most daily spreads and all but stops arbitrage.

## Emissions

With carbon intensity $e_t$ in gCO2/kWh, a battery or site's net emissions are
$-\sum_t e_t\, x_t\, \Delta t / 1000$ tCO2 for net export $x_t$: exports displace grid
generation and imports add to it. Negative means net emissions avoided.

`carbon.price_per_t` steers dispatch by adding $\lambda \hat e_t / 1000$ to the planning
price. For the GB 2019 battery (`examples/gb-2019-carbon.yaml` at £50/t):

| Carbon price | Revenue | Net emissions |
|-------------:|--------:|--------------:|
| £0/t | £13,444 | −19.4 tCO2 |
| £50/t | £13,293 | −21.2 tCO2 |
| £200/t | £12,619 | −23.3 tCO2 |

Even without a carbon price, price arbitrage avoids emissions, because GB prices and
carbon intensity move together (correlation 0.62). Each further tonne costs more: about
£84 per tonne at £50/t and £211 at £200/t.

!!! warning "Average, not marginal"
    These use NESO's average grid intensity. Storage changes the marginal plant, whose
    emissions can differ, so results show direction and rough scale, not causal impact.

!!! info "Why not NESO's forecast?"
    NESO's archived `forecast` is the last forecast issued before each half-hour, not the
    one available the day before. Planning on it at noon the day before raised the
    battery's revenue as the carbon price rose, which only leaked information can do. By
    default dispatch plans on the same hour's actual intensity a week earlier, cut off at
    the decision time like prices; `planning: actual` is an explicit upper bound.
