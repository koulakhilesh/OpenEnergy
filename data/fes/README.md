# NESO Future Energy Scenarios

Written unchanged by `scripts/fetch_fes.py` (`uv run python scripts/fetch_fes.py`).
Downloaded on 2026-10-13. OpenEnergy is not affiliated with or endorsed by NESO.

| File | Edition | Rows | Years | Pathway column |
|------|---------|------|-------|----------------|
| `fes2025_es1.csv` | FES: Pathways to Net Zero 2025, Electricity Supply Data Table (ES1), v006 | 620 | 2024-2050 | `Pathway`: Holistic Transition, Electric Engagement, Hydrogen Evolution, Falling Behind, Ten Year Forecast |
| `fes2025_ed1.csv` | FES 2025, Electricity Demand Summary (ED1) | 250 | 2023-2050 | `Pathway` (as above) |
| `tyo2026_es1.csv` | 2026 Ten Year Outlook, ES1 | 125 | 2025-2036 (2024 blank) | `Scenario`: Ten Year Outlook |
| `tyo2026_ed1.csv` | 2026 Ten Year Outlook, ED1 | 35 | 2025-2036 | `Scenario`: Ten Year Outlook |

Sources: National Energy System Operator (NESO),
*Future Energy Scenarios: Electricity Supply Data Table (ES1)*,
<https://www.neso.energy/data-portal/future-energy-scenario-electricity-supply-data-table-es1>,
and *FES: Electricity Demand Summary Data Table (ED1)*,
<https://www.neso.energy/data-portal/fes-electricity-demand-summary-data-table-ed1>.
Licence: [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence).
Supported by National Energy SO Open Data.

## What OpenEnergy uses

ES1 `Capacity (MW)` and `Storage Capacity (GWh)` summed over connection levels by `Type`,
and the annual (fiscal-year) system demand from ED1: `GBFES System Demand: Total` in FES
2025, `Total System Demand` in the Ten Year Outlook. `system.fes` scales the weather year's
system by the ratio of the chosen year to the weather year in the same pathway; see the
[forward scenarios guide](../../docs/guides/forward-scenarios.md). ES1's `Import (TWh)`,
`Export (TWh)` and `Curtailment (TWh)` are used only to compare with the model's results
(`data/scenarios/fes_summary.csv`).

Known issues: FES 2025's 2025 column is already a projection and differs by pathway (for
example 8.4 to 12.9 GW of batteries), so the same weather year gives each pathway a
slightly different starting point. The Ten Year Outlook has no 2024 values, so it needs a
weather year from 2025. FES publishes no fuel or carbon price paths, and no storage
efficiencies.
