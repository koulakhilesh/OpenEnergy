# Research with the Python API

Every step of a scenario is a plain function, so experiments that do not fit a YAML file
are a few lines of Python.

## How much is a better forecast worth?

[`examples/forecast_error_sweep.py`](https://github.com/koulakhilesh/OpenEnergy/blob/main/examples/forecast_error_sweep.py)
adds Gaussian error of increasing size to the actual 2019 GB prices and measures the
share of perfect-foresight revenue a 1 MW / 2 MWh battery keeps:

```python
raw = OPSDCsvSource(DATA).prices("GB_GBN", date(2019, 1, 1), date(2019, 12, 31))
prices, _ = fill_gaps(raw, max_gap_hours=2)
battery = BatterySpec(power_mw=1, energy_mwh=2)
config = BacktestConfig(dispatch=DispatchConfig(degradation_cost=5))
benchmark = run_backtest(battery, prices, PerfectForesight(prices), config)

for error_std in (0.0, 2.0, 5.0, 10.0, 20.0):
    forecaster = NoisyForesight(prices, error_std=error_std, seed=1)
    summary = summarise(run_backtest(battery, prices, forecaster, config), benchmark)
```

| Error std (GBP/MWh) | Revenue (GBP) | Capture | Cycles |
|--------------------:|--------------:|--------:|-------:|
| 0 | 19,235 | 100.0% | 468 |
| 2 | 18,846 | 98.0% | 494 |
| 5 | 17,261 | 89.7% | 602 |
| 10 | 10,626 | 55.2% | 903 |
| 20 | −164 | −0.9% | 1,309 |

Beyond about £5/MWh of error the optimiser starts trading noise: cycles double and revenue
collapses. The noise here is independent hour to hour, which is harsher than real forecast
errors; a correlated error model is a natural next experiment.

## How good is OpenEnergy's forecast?

The `fundamentals` forecaster (v6.0, [Concepts](../concepts.md#forecasters)) plans each
day at noon the day before on what was published by then: NESO's day-ahead demand
forecast, Elexon's day-ahead wind forecast, the daily gas price and the prices of every
auction that had cleared. A new model is trained each month on everything known before
the month began.
[`examples/fundamentals_forecast.py`](https://github.com/koulakhilesh/OpenEnergy/blob/main/examples/fundamentals_forecast.py)
backtests a 1 MW / 2 MWh battery (95% each way, £5/MWh wear in the plan) on Ember's GB
prices with it and with last week's prices (2026 to 28 October):

| Year | Perfect foresight (£) | Last week's prices (£) | Capture | MAE (£/MWh) | OpenEnergy forecast (£) | Capture | MAE (£/MWh) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2019 | 19,702 | 14,074 | 71.4% | 6.1 | 15,281 | 77.6% | 3.9 |
| 2020 | 22,623 | 17,362 | 76.7% | 7.7 | 18,607 | 82.2% | 4.6 |
| 2021 | 90,264 | 75,065 | 83.2% | 31.3 | 71,665 | 79.4% | 26.3 |
| 2022 | 103,705 | 77,954 | 75.2% | 61.4 | 81,135 | 78.2% | 33.9 |
| 2023 | 46,440 | 36,362 | 78.3% | 20.0 | 39,840 | 85.8% | 11.8 |
| 2024 | 39,412 | 29,128 | 73.9% | 19.5 | 33,894 | 86.0% | 9.3 |
| 2025 | 44,974 | 36,208 | 80.5% | 21.8 | 39,745 | 88.4% | 10.6 |
| 2026 | 41,424 | 32,838 | 79.3% | 27.7 | 36,827 | 88.9% | 14.3 |

What this shows:

- **The error roughly halves, the revenue gap closes by a third to a half.** From 2023
  the forecast's mean absolute error is 48–59% of last week's, and the battery keeps 86–89%
  of the perfect-foresight revenue instead of 74–81%. A battery is paid for the day's
  shape, not its level, so a smaller error buys less revenue than it seems to.
- **2021 is the exception.** Gas prices rose through 2021 faster than a model trained on
  the calmer years before each month could follow; last week's prices carried the new
  level with them and kept 83.2% against 79.4%. By 2022 the forecast was ahead again.
- **A plain model forecasts too flat a day.** Each month the forecast's shape around its
  mean is stretched by 1, 1.25, 1.5, 1.75 or 2, whichever would have earned a reference
  battery most over the previous 90 days (past data only). It chose 1 in 64 of the 94
  months, 1.25 in 24 and 1.5 in 6.
- **Planning one day ahead still pays.** With `dispatch.lookahead_days: 1` on
  `examples/gb-2022-naive.yaml`'s battery, the forecast earns 5.0% (2021) to 13.4% (2019)
  more.

The bundled forecast (`data/forecasts/`) is exactly what a backtest with
`forecast: fundamentals` computes, so `forecast: {method: fundamentals, path: ...}` gives
the same results without training (a test checks a week of it against a live run). What
the forecast may know is tested too: a later wind forecast or a price after the decision
time changes nothing.

## Can reinforcement learning do better?

A reinforcement-learning agent can learn to trade directly, without a forecast and an
optimiser. In the v6.0 design work an agent (PPO, Stable-Baselines3, 0.4 and 3 million
steps) saw exactly what the optimiser sees at noon the day before: an earlier version of
OpenEnergy's forecast for the day, the hour and the energy stored. Trained on 2021–2023
and tested on 2024–2026, it kept 27–38% of the perfect-foresight revenue; the optimiser
planning on the same forecast kept 78–83%. More training did not close the gap. The
optimiser solves the day exactly; the agent has to rediscover that, from noisy rewards.

So OpenEnergy keeps "forecast, then optimise", and ships the test as an environment for
anyone who wants to try (`pip install 'openenergy[rl]'`, Gymnasium):

```python
from openenergy.rl import BatteryTradingEnv, episodes, optimiser_baseline, policy_revenue

days = episodes(prices, NaiveLastWeek(), dates)  # forecasts as the backtest makes them
env = BatteryTradingEnv(days, BatterySpec(power_mw=1, energy_mwh=2), wear=5.0)
baseline = optimiser_baseline(days, env.battery)  # GBP per day, the bar to beat
mine = policy_revenue(env, lambda observation: agent(observation))
```

Each episode is a day: the action is the share of power to sell (positive) or buy, the
reward is the hour's revenue at the actual price less wear, and ending the day away from
the starting energy is settled at the day's mean price plus £20/MWh. A policy that replays
the optimiser's plan earns exactly the baseline (tested).

## Do solar and wind earn the average price?

`openenergy capture` compares what each technology earned per MWh with the plain average
price, per year:

| Year | Solar capture rate | Wind capture rate |
|-----:|-------------------:|------------------:|
| 2015 | 105.9% | 96.4% |
| 2016 | 94.2% | 96.3% |
| 2017 | 93.8% | 99.5% |
| 2018 | 98.3% | 99.2% |
| 2019 | 96.1% | 98.1% |

In GB day-ahead prices up to 2019, neither technology was heavily cannibalised: both
earned within about 6% of baseload, and almost no output fell in negative-price hours (GB
had only 81 such hours in the whole extract). Solar's 2015 premium reflects output
coinciding with daytime peaks. OPSD's solar capacity factors run high because reported
capacity lags new build (see [Data](../data.md)), which affects capacity factor but not
capture rate.

## How big should a shared connection be?

[`examples/colocation_grid_sweep.py`](https://github.com/koulakhilesh/OpenEnergy/blob/main/examples/colocation_grid_sweep.py)
puts 10 MW of solar and a 5 MW / 10 MWh battery behind one connection of increasing size
and compares each with the same assets on separate connections (15 MW in total), for GB
2019 with last week's prices:

| Shared limit (MW) | Site (GBP) | Separate (GBP) | Difference |
|------------------:|-----------:|---------------:|-----------:|
| 5.0 | 590,314 | 618,256 | −27,942 |
| 7.0 | 615,787 | 618,256 | −2,469 |
| 10.0 | 618,093 | 618,256 | −163 |
| 12.5 | 618,243 | 618,256 | −13 |
| 15.0 | 618,244 | 618,256 | −12 |

A battery added behind the solar farm's own 10 MW connection gives up only £163 a year:
solar output and battery discharge rarely need the connection at the same time. From
12.5 MW the gap (£12–13, two parts in 100,000) is within the solver's tolerance. Shrinking
the shared connection below the plant's capacity starts to cost real money, so the saving
on connection capacity has to exceed these figures. Plans use actual solar output, so
these are upper bounds.

## Is planning under price uncertainty worth it?

[`examples/stochastic_value.py`](https://github.com/koulakhilesh/OpenEnergy/blob/main/examples/stochastic_value.py)
plans each day at noon the day before in four ways and settles every plan at actual GB
prices (Ember). The scenarios are last week's prices plus each of that forecast's daily
errors over the last 28 days. Revenue is after a £5/MWh wear cost, for a 1 MW / 2 MWh
battery:

| Year | Plan | Revenue (£) | vs forecast | Loss days |
|---|---|---:|---:|---:|
| 2019 | One forecast (last week) | 4,640 | | 82 |
| 2019 | Scenario mean (risk-neutral) | 4,315 | −7.0% | 90 |
| 2019 | Half CVaR (worst 10%) | 3,412 | −26.5% | 78 |
| 2019 | Full CVaR | 2,221 | −52.1% | 63 |
| 2019 | One forecast, one day lookahead | 6,391 | +37.7% | 83 |
| 2022 | One forecast | 64,610 | | 9 |
| 2022 | Scenario mean | 62,100 | −3.9% | 12 |
| 2022 | Half CVaR | 50,311 | −22.1% | 34 |
| 2022 | Full CVaR | 40,613 | −37.1% | 40 |
| 2022 | One forecast, one day lookahead | 71,213 | +10.2% | 43 |
| 2024 | One forecast | 17,642 | | 34 |
| 2024 | Scenario mean | 16,927 | −4.1% | 45 |
| 2024 | Half CVaR | 12,163 | −31.1% | 43 |
| 2024 | Full CVaR | 8,873 | −49.7% | 44 |
| 2024 | One forecast, one day lookahead | 21,171 | +20.1% | 46 |

What this shows:

- **A risk-neutral scenario plan is just another forecast.** The plan is fixed before
  prices clear and paid at actual prices, so revenue is linear in price: the expected
  revenue of any plan is its revenue at the mean scenario, and the best plan over the
  scenarios is the best plan for their mean. These scenarios shift last week's prices by
  their recent average error, which made the forecast slightly worse every year. With
  only a day-ahead market, the value of the stochastic solution is zero by construction.
  A prototype that also re-planned the next day per scenario (two-stage, not part of the
  example) gained under £1 a year over the same two-day plan on the mean scenario.
- **Risk aversion costs revenue and does not reliably cut bad days.** Weighting the worst
  10% of scenarios (CVaR) loses 22–52% of revenue; in 2022 it more than tripled the days
  with a loss.
- **A longer horizon pays.** Planning today with tomorrow's forecast, rather than
  returning to the same charge every midnight, adds 10–38% after wear cost. Loss days rise
  because a day that fills the battery for tomorrow books the cost today and the revenue
  tomorrow.

The lookahead across all years, with `examples/gb-2022-naive.yaml` (last week's prices,
£5/MWh wear cost in the plan) and `dispatch.lookahead_days` set; revenue per MW-year before
wear cost, perfect foresight with the same lookahead:

| Year | Revenue, 0 days | 1 day | Change | Capture, 0 days | 1 day | Cycles, 0 days | 1 day |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2017 | 20,633 | 22,326 | +8.2% | 78.6% | 80.5% | 526 | 524 |
| 2018 | 18,887 | 20,557 | +8.8% | 74.4% | 76.5% | 529 | 526 |
| 2019 | 13,943 | 15,818 | +13.4% | 71.4% | 74.7% | 468 | 474 |
| 2020 | 17,144 | 19,669 | +14.7% | 76.7% | 80.5% | 419 | 428 |
| 2021 | 74,169 | 78,259 | +5.5% | 83.1% | 84.8% | 620 | 600 |
| 2022 | 76,948 | 82,938 | +7.8% | 75.0% | 76.8% | 661 | 627 |
| 2023 | 35,957 | 40,093 | +11.5% | 78.2% | 81.5% | 612 | 585 |
| 2024 | 28,690 | 31,860 | +11.0% | 73.8% | 76.8% | 569 | 551 |
| 2025 | 35,861 | 38,937 | +8.6% | 80.5% | 82.7% | 571 | 547 |

One day of lookahead adds 5.5–14.7% revenue every year, and from 2021 does so with fewer
cycles. Two or three days change revenue by under £20 a year: last week's prices say little
about the day after tomorrow.

Uncertainty could matter when a later decision can react to prices, such as balancing or
frequency response. [Revenue stacking](revenue-stacking.md) checks both: response
availability is also committed before its price is known, so the same argument applies;
balancing does give the battery a later decision, but without an imbalance-price forecast,
which open data does not provide, it gains in some years and loses in others. The lookahead is a scenario setting,
`dispatch.lookahead_days`.

## Building blocks

| Step | Function |
|------|----------|
| Load prices | `OPSDCsvSource(path).prices(zone, start, end)` |
| Load capacity factors | `OPSDCsvSource(path).profile(zone, technology, start, end)` |
| Fill short gaps | `fill_gaps(series, max_gap_hours)` |
| Plan one horizon | `optimise_dispatch(spec, state, prices, step_hours, config)` |
| Apply a plan | `apply_dispatch(spec, state, charge_mw, discharge_mw, step_hours)` |
| Age a battery | `age(spec, state, hours)` |
| Backtest | `run_backtest(spec, prices, forecaster, config, days)` |
| Plant output | `RenewableSpec(technology, capacity_mw).generation_mw(profile)` |
| Co-located backtest | `run_backtest(..., site=Site(output, GridConnection(...)))` |
| Plant on its own | `run_plant_backtest(site, prices, forecaster, config, days)` |
| Captured price | `capture_metrics(prices, output, capacity_mw)`, `capture_by_year(prices, profile)` |
| Summarise | `summarise(result, benchmark)` |

Any object with a `name` and a `forecast(history, index)` method is a forecaster, so a new
model needs no changes to the library. See the [API reference](../api.md).
