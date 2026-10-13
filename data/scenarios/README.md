# Precomputed FES scenario prices

Model output, not source data: written by `scripts/build_scenario_prices.py` (needs the
`system` extra) on 2026-10-13 with OpenEnergy 4.0.0, for the web app and the
[forward scenarios guide](../../docs/guides/forward-scenarios.md). Rebuild after changing
the model or its inputs.

Each NESO FES pathway's 2030 and 2035 system is solved on 2025's weather, demand shape and
fuel, carbon and neighbouring prices, with price-taking interconnector links and default
assumptions, exactly as `openenergy system run` with `interconnectors: links` and
`fes: {pathway, year}` would.

## `fes_prices.csv`

Hourly modelled GB price, GBP/MWh, 2025-01-01 00:00 to 2025-12-31 23:00 UTC (8,760 rows).
Columns: `utc_timestamp` and one per pathway and year, for example
`holistic_transition_2030`.

## `fes_summary.csv`

One row per pathway and year: the model's mean price, mean daily spread (max minus min),
interconnector imports and exports, curtailment, unserved energy and fossil emissions,
next to FES's own interconnector imports and exports and curtailment for the same year
(`fes_*` columns, from ES1).

Built from: NESO Future Energy Scenarios 2025 and 2026 Ten Year Outlook (ES1, ED1), NESO
historic generation mix and Interconnector Register (NESO Open Data Licence v1.0,
supported by National Energy SO Open Data); DESNZ DUKES and Quarterly Energy Prices (Open
Government Licence v3.0); World Bank carbon prices (CC BY 4.0); HMRC carbon price support
rates (Open Government Licence v3.0); Ember day-ahead prices (CC BY 4.0) at ECB reference
rates; Elexon BMRS FUELHH (contains BMRS data © Elexon Limited copyright and database
right 2026). See each folder's README for details. The model and its limits are described
in the guide; these are scenario results, not forecasts.
