# What is known before the day-ahead auction

Written by `scripts/fetch_fundamentals.py` (or `openenergy data update --fundamentals`,
which writes the same files to a user cache). Downloaded on 2026-10-30. OpenEnergy is not
affiliated with or endorsed by any of the sources below.

The system model uses the daily gas price; the `fundamentals` price forecast uses all
three files, each only as it was known at the decision time (by default noon UTC the day
before).

## `gas_sap_daily.csv`

Daily System Average Price (SAP) of gas, Great Britain, pence per kWh, 2018-01-01 to
2026-10-25 (3,220 days, no gaps). Columns: `date` (gas day) and `sap_p_per_kwh`.

Source: Office for National Statistics, *System Average Price (SAP) of gas*, table 1
(daily), from National Gas Transmission,
<https://www.ons.gov.uk/economy/economicoutputandproductivity/output/datasets/systemaveragepricesapofgas>.
Licence: [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
ONS publishes it as official statistics in development.

Changes: only the daily column is kept; dates written as ISO 8601; values unchanged.
OpenEnergy multiplies by 10 for GBP per MWh of gas.

Known issues: SAP is the average price of gas traded on the On-the-Day Commodity Market,
a wholesale price; it excludes the network charges power stations pay, which DESNZ's
quarterly price (the model's input before 2018) includes. A gas day runs 05:00 to 05:00 UK
time; OpenEnergy applies each gas day's price to the UTC calendar day of the same date.
Highest: 19.39 p/kWh on 29 August 2022.

## `neso_demand_day_ahead.csv`

NESO's day-ahead national demand forecast at its cardinal points (the day's peaks,
troughs and turning points), 2018-01-02 to 2026-11-01 (58,792 points from 4,980 forecast
issues). Columns: `target_utc` (UTC, the middle of each point's window), `demand_mw` and
`issued_utc` (when NESO published the forecast).

Source: NESO, *Day Ahead Demand Forecast*, file *Historic Day Ahead Demand Forecasts*,
<https://www.neso.energy/data-portal/1-day-ahead-demand-forecast>. Licence:
[NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence).
Supported by National Energy SO Open Data.

Changes: only forecasts one day ahead are kept; each point's window (UK clock time,
HHMM) is turned into its middle in UTC; points in the hour the clocks go back are
ambiguous and dropped. OpenEnergy interpolates linearly between points, never across more
than six hours.

Known issues: the forecast is of transmission demand, which excludes demand met by
embedded wind and solar. Against transmission demand estimated from NESO's generation
mix, it lines up best when moved one hour earlier (correlation 0.957 against 0.918 as
published, January–February 2024; the same in summer), so the published times may run an
hour late; the times are used as published. Most forecasts are issued at about 08:45 UTC
the day before; 5.6% of 2019's hours have no forecast issued by noon the day before.

## `elexon_wind_day_ahead.csv`

Elexon's hourly wind generation forecast (transmission-connected, metered wind), the
latest issued by noon UTC the day before each hour, 2018-01-02 to 2026-11-01 (76,970
hours; 452 hours without such a forecast). Columns: `target_utc`, `wind_mw` and
`issued_utc`.

Source: Elexon, BMRS Insights API, *Wind generation forecast* (dataset WINDFOR),
<https://bmrs.elexon.co.uk/>, reused under the
[BMRS data licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/).
Contains BMRS data © Elexon Limited copyright and database right 2026.

Changes: of the forecasts Elexon publishes four times a day, only the latest published
by noon UTC the day before each hour is kept; values unchanged (MW).

Known issues: NESO also publishes a historic day-ahead wind forecast, but its archive keeps
only the last forecast for each half-hour, often issued on the day itself (31% of 2026's
hours had one issued by noon the day before), so it would leak information a
day-ahead plan cannot have. Elexon keeps every issue with its time.
