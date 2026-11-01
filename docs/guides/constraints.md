# Transmission constraints

GB has one national wholesale price ([DESNZ, REMA summer update, July
2025](https://www.gov.uk/government/publications/review-of-electricity-market-arrangements-rema-summer-update-2025)),
and OpenEnergy models GB as one bus. The transmission network does not behave like one:
when wind in the north exceeds what the lines south can carry, NESO pays generators on one
side of the boundary to turn down and others to turn up. That changes balancing costs and
where a battery helps, not the day-ahead price. This page collects what open data says
about it, before any model of it (`data/constraints/`, written by
`scripts/fetch_constraints.py`).

## What constraints cost

NESO's daily constraint costs, by financial year (April to March), GBP million:

| Year | Thermal | Voltage | System inertia | Largest loss | Total | Thermal volume (TWh, net) |
|---|---:|---:|---:|---:|---:|---:|
| 2021/22 | 1,134 | 111 | 60 | 115 | 1,420 | −3.9 |
| 2022/23 | 1,504 | 141 | 104 | 6 | 1,754 | −4.1 |
| 2023/24 | 1,040 | 268 | 83 | 0 | 1,390 | −6.3 |
| 2024/25 | 1,710 | 154 | 41 | 0 | 1,905 | −12.1 |
| 2025/26 | 1,956 | 212 | 41 | 0 | 2,210 | −14.0 |
| 2026/27 (to 21 October) | 1,607 | 171 | 31 | 0 | 1,808 | −7.7 |

Thermal constraints (lines at their limit) are 75–90% of the cost. The net energy turned
down for them more than tripled from 2022/23 to 2025/26, from 4.1 to 14.0 TWh, while their
cost rose by 30%, so the cost per MWh of net volume fell from about £370 to £140.

## How often the boundaries are full

NESO publishes, a day ahead, each boundary group's limit and flow for every half-hour (from
2023). Share of half-hours with the flow at or above 95% of the limit, for the groups
published in most half-hours:

| Boundary group | 2023 | 2024 | 2025 | 2026 (to October) |
|---|---:|---:|---:|---:|
| SCOTEX | 0.4% | 25.4% | 34.0% | 41.9% |
| SSHARN (2023), SSHARN3 | 22.1% | 40.8% | 32.5% | 48.9% |
| SSE_SP (2023), SSE_SP2 | 8.2% | 49.3% | 42.4% | 53.7% |
| SSEN_S | 6.3% | 34.0% | 44.8% | 51.8% |
| HARSPNBLY | 9.1% | 35.2% | 38.4% | 42.2% |
| NKILGRMO | 15.0% | 30.9% | 40.4% | 30.4% |
| FLOWSTH | 0.6% | 4.7% | 5.6% | 7.4% |
| GM_SNOW5A | 2.2% | 6.1% | 4.7% | 5.0% |
| SEIMP (2023), SEIMPPR23 | 0.0% | 2.4% | 3.9% | 3.9% |

Six groups are at their limit a third to a half of the time from 2024; three seldom are.
NESO's network diagrams, published with the data, show where each boundary runs. One
caution: in 2023 almost no flow is above its limit, and from 2024 a fifth to a half are in
the first six groups. NESO's description does not say whether the published flow is before
or after its actions, so part of the jump may be in what is published. Group names also
change (`SSHARN` became `SSHARN3`).

## Scotland and England & Wales

Most of GB's wind is in Scotland and most of its demand is not. NESO's historic demand data
split national demand into England and Wales and the rest, and from 2023 publish the flow
from Scotland to England and Wales (the transfer across the B6 boundary); DESNZ's
Renewable Energy Planning Database gives where the grid-scale capacity is (`data/zones/`,
`scripts/fetch_zones.py`):

| Year | Scotland's demand (mean GW) | Transfer south (mean GW) | Transfer, 95th percentile / highest (GW) | Half-hours exporting south | Energy sent south (TWh) |
|---|---:|---:|---:|---:|---:|
| 2023 | 2.19 | 1.36 | 4.53 / 6.24 | 71% | 13.3 |
| 2024 | 2.13 | 1.96 | 5.26 / 6.70 | 83% | 18.2 |
| 2025 | 2.16 | 2.11 | 4.96 / 6.59 | 86% | 19.3 |
| 2026 (to 10 Oct) | 2.05 | 2.34 | 5.06 / 6.71 | 91% | 16.2 |

| Grid-scale capacity at the end of 2025 (GW) | Scotland | England and Wales |
|---|---:|---:|
| Onshore wind | 10.1 | 4.1 |
| Offshore wind | 4.3 | 11.7 |
| Batteries | 0.6 | 3.6 |
| Solar (over 150 kW) | 0.1 | 10.4 |

Scotland uses about 2.2 GW on average and has over 14 GW of wind, so it sends power south
most of the time, more each year, and the transfer tops out near 6.7 GW. What a battery
north or south of the boundary actually earns is on [Real batteries](real-batteries.md#north-and-south-of-the-border).

## What this means for OpenEnergy

- Day-ahead prices are national, so constraints do not change the backcasts or the
  battery values on day-ahead prices.
- They do change where storage is worth most to the system: a battery on the exporting
  side of a full boundary can absorb wind that would otherwise be paid to turn down.
  v7.0 measures this from what real batteries in each zone earned; a two-zone dispatch
  model, checked against the transfer above, is planned for v7.1.
- FES curtailment in the [forward scenarios](forward-scenarios.md) is curtailment on one
  bus; a real network would curtail more.

## Sources

NESO, *Constraint Breakdown Costs and Volume*, *Day Ahead Constraint Flows and Limits* and
*Historic Demand Data*,
[NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence),
supported by National Energy SO Open Data (accessed 31 October 2026). Department for
Energy Security and Net Zero, *Renewable Energy Planning Database*, July 2026,
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Details and known issues in `data/constraints/README.md` and `data/zones/README.md`.
