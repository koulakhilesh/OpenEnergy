# Model forecasts

Model output, not source data: written by `scripts/build_fundamentals_forecast.py` so the
web app, the docs and scenarios can plan on the fundamentals forecast without retraining
it (`forecast: {method: fundamentals, path: ...}`). Built on 2026-10-30 with OpenEnergy
6.0.0.

## `gb_fundamentals_day_ahead.csv`

OpenEnergy's day-ahead forecast of the GB hourly day-ahead price, every hour from
2019-01-01 to 2026-10-28 (68,592 hours). Columns: `utc_timestamp`,
`forecast_gbp_per_mwh` and `stretch` (the factor chosen for that month).

How it was made: for each day, exactly what a backtest with `forecast: fundamentals`
forecasts at noon UTC the day before (`lead_hours: 12`, `information: auction`). One
gradient-boosting model per month learns how each hour's price differs from the mean of
the last 24 known prices, from the prices of one, two and seven days before, the day-ahead
demand and wind forecasts, the daily gas price and the calendar; it trains on everything
known before the month began, from 15 January 2018. Each month's stretch (how far the
forecast day is pulled away from its mean: 1, 1.25, 1.5, 1.75 or 2) is the one that would
have earned a reference battery the most over the 90 days before the month. It is
deterministic (seed 0): `tests/forecast/test_fundamentals.py` checks a week of this file
against a live run. The month's model chose a stretch of 1 in 64 months, 1.25 in 24 and
1.5 in 6.

Inputs: GB day-ahead prices from Ember (`data/prices/gb_day_ahead_ember.csv`,
CC BY 4.0) and the files in `data/fundamentals/` (ONS daily gas price, Open Government
Licence v3.0; NESO day-ahead demand forecast, NESO Open Data Licence v1.0, supported by
National Energy SO Open Data; Elexon day-ahead wind forecast, contains BMRS data © Elexon
Limited copyright and database right 2026). The forecast is released with OpenEnergy under
its MIT licence; the attribution for the inputs still applies.

How well it does: `examples/fundamentals_forecast.py` backtests a 1 MW / 2 MWh battery on
it and on last week's prices. It captures more of the perfect-foresight revenue than last
week's prices in every year except 2021, when gas prices rose faster than any model trained
on the calmer years before could follow; see the research guide.
