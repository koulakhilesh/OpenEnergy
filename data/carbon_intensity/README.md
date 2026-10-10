# GB national carbon intensity

`gb_national.csv`: half-hourly national carbon intensity of Great Britain's electricity
system, 2018-01-01 00:00 to 2025-12-31 23:30 UTC (140,256 rows, one per half-hour).

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

Downloaded on 2026-10-10 with `scripts/fetch_carbon_intensity.py`; values are stored
exactly as returned by the API. The 179 half-hours the API did not return (the longest run
about 45 hours, from 2023-10-20 22:00) are written with both values blank. Methodology:
[national forecast](https://www.neso.energy/data-portal/national-carbon-intensity-forecast/national_carbon_intensity_forecast_methodology).

## Known issues

- 804 half-hours have no `actual` value (18 runs, the longest about three days); 438 of
  them are before October 2020. 222 have no `forecast`.
- 16 `forecast` values are implausible (up to 13,579 gCO2/kWh). OpenEnergy treats any
  value outside 0–1000 gCO2/kWh as missing when loading.
- Values are average intensities, not marginal emission factors.
