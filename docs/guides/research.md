# Research with the Python API

Every step of a scenario is a plain function, so experiments that do not fit a YAML file
are a few lines of Python.

## How much is a better forecast worth?

[`examples/forecast_error_sweep.py`](https://github.com/koulakhilesh/OpenEnergy/blob/master/examples/forecast_error_sweep.py)
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

[`examples/colocation_grid_sweep.py`](https://github.com/koulakhilesh/OpenEnergy/blob/master/examples/colocation_grid_sweep.py)
puts 10 MW of solar and a 5 MW / 10 MWh battery behind one connection of increasing size
and compares each with the same assets on separate connections (15 MW in total), for GB
2019 with last week's prices:

| Shared limit (MW) | Site (GBP) | Separate (GBP) | Difference |
|------------------:|-----------:|---------------:|-----------:|
| 5.0 | 590,250 | 618,231 | −27,981 |
| 7.0 | 615,736 | 618,231 | −2,494 |
| 10.0 | 618,208 | 618,231 | −23 |
| 12.5 | 618,236 | 618,231 | 5 |
| 15.0 | 618,249 | 618,231 | 18 |

A battery added behind the solar farm's own 10 MW connection gives up only £23 a year:
solar output and battery discharge rarely need the connection at the same time. Shrinking
the shared connection below the plant's capacity starts to cost real money, so the saving
on connection capacity has to exceed these figures. Plans use actual solar output, so
these are upper bounds.

## Is planning under price uncertainty worth it?

[`examples/stochastic_value.py`](https://github.com/koulakhilesh/OpenEnergy/blob/master/examples/stochastic_value.py)
plans each day at noon the day before in four ways and settles every plan at actual GB
prices (Ember). The scenarios are last week's prices plus each of that forecast's daily
errors over the last 28 days. Revenue is after a £5/MWh wear cost, for a 1 MW / 2 MWh
battery:

| Year | Plan | Revenue (£) | vs forecast | Loss days |
|---|---|---:|---:|---:|
| 2019 | One forecast (last week) | 4,635 | | 83 |
| 2019 | Scenario mean (risk-neutral) | 4,315 | −6.9% | 90 |
| 2019 | Half CVaR (worst 10%) | 3,412 | −26.4% | 78 |
| 2019 | Full CVaR | 2,221 | −52.1% | 63 |
| 2019 | One forecast, one day lookahead | 6,400 | +38.1% | 83 |
| 2022 | One forecast | 64,602 | | 9 |
| 2022 | Scenario mean | 62,100 | −3.9% | 12 |
| 2022 | Half CVaR | 50,311 | −22.1% | 34 |
| 2022 | Full CVaR | 40,613 | −37.1% | 40 |
| 2022 | One forecast, one day lookahead | 71,213 | +10.2% | 43 |
| 2024 | One forecast | 17,633 | | 34 |
| 2024 | Scenario mean | 16,927 | −4.0% | 45 |
| 2024 | Half CVaR | 12,163 | −31.0% | 43 |
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
| 2017 | 20,682 | 22,356 | +8.1% | 78.8% | 80.6% | 526 | 524 |
| 2018 | 18,889 | 20,567 | +8.9% | 74.4% | 76.5% | 529 | 526 |
| 2019 | 13,936 | 15,827 | +13.6% | 71.3% | 74.7% | 468 | 474 |
| 2020 | 17,155 | 19,661 | +14.6% | 76.7% | 80.5% | 419 | 428 |
| 2021 | 74,172 | 78,277 | +5.5% | 83.1% | 84.8% | 620 | 600 |
| 2022 | 76,940 | 82,938 | +7.8% | 75.0% | 76.8% | 661 | 627 |
| 2023 | 35,964 | 40,091 | +11.5% | 78.2% | 81.5% | 612 | 585 |
| 2024 | 28,677 | 31,864 | +11.1% | 73.8% | 76.9% | 569 | 551 |
| 2025 | 35,861 | 38,936 | +8.6% | 80.5% | 82.7% | 571 | 547 |

One day of lookahead adds 5.5–14.6% revenue every year, and from 2021 does so with fewer
cycles. Two or three days change revenue by under £20 a year: last week's prices say little
about the day after tomorrow.

Uncertainty becomes valuable when a later decision can react to prices, such as intraday
trading, balancing or frequency response; that is planned with revenue stacking. The
lookahead is a scenario setting, `dispatch.lookahead_days`.

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
