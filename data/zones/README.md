# GB zones: Scotland and England & Wales

Written by `scripts/fetch_zones.py` (downloaded 2026-10-31). OpenEnergy is not affiliated
with or endorsed by NESO or DESNZ.

## `demand_by_zone.csv`

Each UTC half-hour from 2019-01-01 to 2026-10-10: national demand (`national_demand_mw`,
NESO's ND), England and Wales demand, Scotland's demand (their difference), the transfer
from Scotland to England and Wales (`scottish_transfer_mw`, the flow across the B6
boundary; published from 2023, blank before), and embedded wind and solar generation and
capacity (MW).

Source: National Energy System Operator (NESO), *Historic Demand Data*, one file per year,
<https://www.neso.energy/data-portal/historic-demand-data>.
Licence: [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence).
Supported by National Energy SO Open Data.
Changes: settlement date and period turned into UTC times; Scotland's demand derived; other
columns dropped.

## `capacity_by_year.csv`

Grid-scale capacity in operation at the end of each year from 2010 by technology
(battery, solar, onshore and offshore wind) and zone (`scotland`, `england_wales`), MW.

Source: Department for Energy Security and Net Zero, *Renewable Energy Planning Database*
(REPD), July 2026 extract,
<https://www.gov.uk/government/publications/renewable-energy-planning-database-monthly-extract>.
Licence: [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Changes: projects with status "Operational" and an operational date, Northern Ireland
excluded, summed by technology, zone and year and accumulated.

Known issues: REPD covers projects over 150 kW (over 1 MW before 2021), so rooftop and
other small solar is missing (NESO's embedded solar capacity above covers it nationally);
decommissioned projects drop out of "Operational", so earlier years can be understated.

## `plant_by_zone.csv`

Major power producers' capacity at the end of each year from 2010 by technology (`ccgt`,
`gas_turbine`, `oil_engine`, `coal`, `nuclear`, `hydro` (natural flow), `pumped_storage`,
`bioenergy`) and zone, MW.

Source: Department for Energy Security and Net Zero, *Digest of UK Energy Statistics
(DUKES)* 2026, table 5.8 (5.8.A and 5.8.C),
<https://www.gov.uk/government/statistics/electricity-chapter-5-digest-of-united-kingdom-energy-statistics-dukes>.
Licence: [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Changes: rows renamed; Northern Ireland dropped. Written by
`uv run --with openpyxl python scripts/fetch_zones.py plant`.

## `two_zones_by_year.csv`

OpenEnergy model output from `openenergy system zones --out`: by year, the mean SCOTEX
limit used, the modelled and recorded mean transfer from Scotland (MW) and their hourly
correlation, the share of hours the model is at the limit and the recorded transfer within
10% of it, the share of hours the zones' prices differ by over GBP 1 and the mean gap,
Scotland's share of wind capacity, and a 1 MW / 2 MWh battery's perfect-foresight revenue
per MW-year on each zone's price. Built from the files above, `data/system/` and
`data/constraints/day_ahead_boundaries_monthly.csv`.
