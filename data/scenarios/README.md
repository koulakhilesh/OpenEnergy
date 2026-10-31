# Precomputed FES scenario prices and the storage saturation study

Model output, not source data, for the web app and the
[forward scenarios guide](../../docs/guides/forward-scenarios.md). Built on 2026-10-31 with
OpenEnergy 6.0.0. Rebuild after changing the model or its inputs.

## `fes_prices.csv` and `fes_summary.csv`

Written by `scripts/build_scenario_prices.py` (needs the `system` extra). Each NESO FES
pathway's 2030 and 2035 system is solved on 2025's weather, demand shape and fuel, carbon
and neighbouring prices (the daily gas price), with price-taking interconnector links, unit
commitment and default assumptions, exactly as `openenergy system run` with
`interconnectors: links`, `commitment: true` and `fes: {pathway, year}` would. That
includes the default secure system: the least firm peaking capacity, in 250 MW steps, that
keeps hours with unserved energy within GB's reliability standard of 3 hours a year.

`fes_prices.csv`: hourly modelled GB price, GBP/MWh, 2025-01-01 00:00 to 2025-12-31 23:00
UTC (8,760 rows). Columns: `utc_timestamp` and one per pathway and year, for example
`holistic_transition_2030`.

`fes_summary.csv`: one row per pathway and year: the model's mean price, mean daily spread
(max minus min), interconnector imports and exports, curtailment, unserved energy and the
hours with any, the firm capacity added (`firm_added_mw`) and fossil emissions, next to
FES's own interconnector imports and exports and curtailment for the same year (`fes_*`
columns, from ES1).

## `saturation.csv` and `saturation_years.csv`

Written by `openenergy system saturation --workers 10 --out data/scenarios`. For each FES
pathway that can be scaled from both weather years (the 2026 Ten Year Outlook publishes no
2024 wind, so it is skipped) and each battery fleet scale (0, 0.5, 1, 2 and 3 times the
pathway's 2035 FES battery power, same duration), the least firm capacity is added that
keeps hours with unserved energy, averaged over the 2024 and 2025 weather years, within 3
hours a year; then a 1 MW / 2 MWh battery (95% each way, GBP 5/MWh wear) is valued with
perfect foresight on each year's modelled prices.

`saturation_years.csv`: one row per pathway, scale and weather year: firm capacity added,
FES battery power, hours and GWh unserved, mean price and daily spread, hours priced at
GBP 1,000/MWh or more and the days with one, curtailment, emissions, the FES fleet's
cycles, and the battery's revenue per MW-year, the part of it earned on those scarcity
days, and its cycles. `saturation.csv`: the mean over the two weather years, with
`lole_hours` (mean hours with unserved energy) and `equivalent_firm` (firm capacity saved
against no FES batteries, per MW of batteries).

Built from: NESO Future Energy Scenarios 2025 and 2026 Ten Year Outlook (ES1, ED1), NESO
historic generation mix and Interconnector Register (NESO Open Data Licence v1.0,
supported by National Energy SO Open Data); DESNZ DUKES and Quarterly Energy Prices and ONS
System Average Price of gas (Open Government Licence v3.0); World Bank carbon prices
(CC BY 4.0); HMRC carbon price support rates (Open Government Licence v3.0); Ember
day-ahead prices (CC BY 4.0) at ECB reference rates; Elexon BMRS FUELHH (contains BMRS data
© Elexon Limited copyright and database right 2026). See each folder's README for details.
The model and its limits are described in the guide; these are scenario results, not
forecasts.
