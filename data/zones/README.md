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
