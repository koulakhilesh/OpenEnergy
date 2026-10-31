# Transmission constraints

Written by `scripts/fetch_constraints.py` on 2026-10-31. Evidence for the
[constraints page](../../docs/guides/constraints.md); the model does not use these files.
OpenEnergy is not affiliated with or endorsed by NESO.

## `constraint_breakdown_daily.csv`

NESO's daily cost (GBP) and volume (MWh) of actions to manage thermal constraints, voltage
constraints, the largest loss and system inertia, 2021-04-01 to 2026-10-21 (2,028 days).
Columns as published: `Date`, then a cost and a volume column for each category.

Source: NESO, *Constraint Breakdown Costs and Volume*,
<https://www.neso.energy/data-portal/constraint-breakdown>, one file per financial year
(April to March) from 2021-2022. Licence:
[NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence).
Supported by National Energy SO Open Data.

Changes: the yearly files are joined and dates written as ISO 8601; values unchanged.

Known issues: volumes are net (negative when more energy is turned down than up); the
2025-2026 file has 364 days.

## `day_ahead_boundaries_monthly.csv`

A monthly summary of NESO's day-ahead limit and flow at each constraint boundary group,
January 2023 to October 2026 (558 rows). Columns: `group` (NESO's boundary group, e.g.
`SCOTEX`, `SSHARN3`), `month`, `half_hours` with a positive limit and a flow,
`limit_mw` and `flow_mw` (means), and `near_limit` and `above_limit`, the shares of those
half-hours with flow at least 95% of the limit and above it.

Source: NESO, *Day Ahead Constraint Flows and Limits*,
<https://www.neso.energy/data-portal/day-ahead-constraint-flows-and-limits>, "a snapshot
of the limits and flows at relevant boundaries at day ahead stage"; the published file
keeps the latest three years and the current one. Licence:
[NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence).
Supported by National Energy SO Open Data.

Changes: summarised by month from the half-hourly file (about 30 MB, not bundled); rows
with a limit of zero or less (874) or no flow (3,365) left out. Times are UK clock time as
published.

Known issues: boundary groups are renamed and redefined over time (`SSHARN` in 2023,
`SSHARN3` from 2024; `SSE_SP` and `SSE_SP2`). In 2023 almost no half-hour has a flow above
its limit (at most 0.1% per group), while from 2024 a fifth to a half do in six groups
(`SCOTEX`, `SSHARN3`, `SSE_SP2`, `SSEN_S`, `HARSPNBLY`, `NKILGRMO`); the dataset's description does not say whether the published flow is before
or after NESO's actions, so this change may be in what is published rather than on the
network.
