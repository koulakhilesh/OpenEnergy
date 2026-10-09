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
