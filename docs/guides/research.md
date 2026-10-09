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

## Building blocks

| Step | Function |
|------|----------|
| Load prices | `OPSDCsvSource(path).prices(zone, start, end)` |
| Fill short gaps | `fill_gaps(series, max_gap_hours)` |
| Plan one horizon | `optimise_dispatch(spec, state, prices, step_hours, config)` |
| Apply a plan | `apply_dispatch(spec, state, charge_mw, discharge_mw, step_hours)` |
| Age a battery | `age(spec, state, hours)` |
| Backtest | `run_backtest(spec, prices, forecaster, config, days)` |
| Summarise | `summarise(result, benchmark)` |

Any object with a `name` and a `forecast(history, index)` method is a forecaster, so a new
model needs no changes to the library. See the [API reference](../api.md).
