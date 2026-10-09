# GB national carbon intensity

`gb_national.csv`: half-hourly national carbon intensity of Great Britain's electricity
system, 2018-01-01 00:00 to 2020-09-30 23:30 UTC (48,192 rows).

| Column | Meaning |
|--------|---------|
| `utc_timestamp` | Start of the half-hour, UTC |
| `forecast` | NESO's forecast intensity, gCO2/kWh |
| `actual` | NESO's estimated actual intensity, gCO2/kWh |

## Source and licence

National Energy System Operator (NESO), Carbon Intensity API,
<https://carbonintensity.org.uk/>. API documentation:
<https://carbon-intensity.github.io/api-definitions/>.

Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); see the
[API terms of use](https://github.com/carbon-intensity/terms). OpenEnergy is not affiliated
with or endorsed by NESO.

Downloaded on 2026-10-09 with `scripts/fetch_carbon_intensity.py`; values are stored
exactly as returned by the API. Methodology:
[national forecast](https://www.neso.energy/data-portal/national-carbon-intensity-forecast/national_carbon_intensity_forecast_methodology).

## Known issues

- 438 half-hours have no `actual` value (nine runs, the longest about three days).
- 16 `forecast` values are implausible (up to 13,579 gCO2/kWh). OpenEnergy treats any
  value outside 0–1000 gCO2/kWh as missing when loading.
- Values are average intensities, not marginal emission factors.
