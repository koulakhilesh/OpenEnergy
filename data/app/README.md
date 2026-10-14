# Precomputed web app results

Model output, not source data: written by `scripts/build_app_results.py` for the
[web app](https://open-energy-eight.vercel.app/), so common requests return at once. Rebuild
after changing the model, the app's battery settings or the bundled data.

Every request in `openenergy.app.results.grid()` is run exactly as the app runs it live:
a 1 MW battery of 1, 2 or 4 hours (95% efficiency each way, £5/MWh wear cost), planned at
noon the day before on last week's prices or with perfect foresight, on

- each GB year 2017-2025 (Ember day-ahead prices at ECB rates), and from 2022 also with
  Dynamic Containment, or Dynamic Containment and Moderation (NESO auction results);
- each NESO FES pathway in 2030 and 2035 (`../scenarios/fes_prices.csv`).

Revenue scales with power at a fixed duration (1, 10 and 50 MW give the same revenue per
MW), so results are per MW.

## `summary.csv`

One row per request (174): `key`, `source`, `year`, `pathway`, `hours`, `forecast`,
`services`, then `days` simulated, `revenue_per_mw_year` and `perfect_per_mw_year` (GBP),
`capture_ratio` (share of the perfect-foresight revenue), `cycles_per_day`,
`captured_spread` (GBP/MWh), `forecast_mae` (GBP/MWh) and `response_share` (share of
revenue from frequency response).

## `daily.csv`

Daily revenue (GBP, for 1 MW) per request: `key`, `date`, `revenue` and
`benchmark_revenue` (perfect foresight on the same day).

Built from the sources credited in `../prices/README.md`, `../response/README.md`,
`../scenarios/README.md` and the folders they list: Ember (CC BY 4.0), ECB reference rates,
NESO (NESO Open Data Licence v1.0, supported by National Energy SO Open Data), and the
DESNZ, HMRC, World Bank, Elexon and other sources behind the FES pathway prices.
