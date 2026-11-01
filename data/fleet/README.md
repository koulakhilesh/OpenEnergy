# Real GB batteries

What GB's grid batteries actually did, written by `scripts/fetch_fleet.py` (raw responses
cached outside the repository) and compared with OpenEnergy's optimiser by
`scripts/real_batteries.py`. OpenEnergy is not affiliated with or endorsed by Elexon.

Source: Elexon, BMRS Insights API (<https://bmrs.elexon.co.uk/>): the BM unit register
(`reference/bmunits/all`), physical notifications (`datasets/PN/stream`), metered output per
BM unit (`datasets/B1610/stream`, the latest settlement run) and indicative Balancing
Mechanism volumes and cashflows (`balancing/settlement/indicative/volumes|cashflows`).
Licence: [BMRS data licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/).
Contains BMRS data © Elexon Limited copyright and database right 2026. Day-ahead prices
(Ember, `data/prices`) and system prices (Elexon, `data/balancing`) keep their own credits.

## `battery_units.csv`

The BM units whose name or lead party names a battery ("battery", "BESS", "energy
storage"), transmission (`T_`) or embedded (`E_`) only, excluding pumped storage and
thermal plant: Elexon unit id, National Grid id, name, lead party, type, registered
generation and demand capacity (MW), GSP group, transmission loss factor (TLF), region and
zone (`scotland` or `england_wales`). Transmission units have no GSP group; each TLF zone
has a single loss factor, so they are placed by matching their TLF with units whose GSP
group is known (blank where no unit matches). Battery duration is not in the register.

## `battery_daily.csv`

One row per unit and UTC day with any PN or metered output, 2021-01-01 to 2026-10-29:

| Column | Meaning |
|---|---|
| `pn_mwh_out`, `pn_mwh_in` | Energy in the unit's physical notification, exported and imported (MWh): its position at gate closure, an hour ahead |
| `pn_value_day_ahead_gbp` | That position valued at the GB day-ahead price |
| `metered_mwh_out`, `metered_mwh_in` | Energy the meter recorded (B1610), exported and imported (MWh) |
| `metered_value_day_ahead_gbp` | Metered energy valued at the day-ahead price: what the unit's physical operation was worth on that market |
| `bm_offer_mwh`, `bm_bid_mwh` | Accepted Balancing Mechanism volumes before tagging (MWh; bids negative) |
| `bm_offer_gbp`, `bm_bid_gbp` | Indicative BM cashflows (GBP; payments to the unit positive) |
| `imbalance_mwh`, `imbalance_gbp` | Metered energy less the PN and accepted BM volumes, and that at the system price |

Changes: PN points averaged over each half-hour (time-weighted); settlement periods
turned into UTC times; values summed by UTC day; battery units only.

## `fleet_hourly.csv`

Each UTC hour: the fleet's metered net output (`metered_net_mw`, export positive), its net
PN (`pn_net_mw`), exports and imports (metered where published, otherwise the PN) and the
number of units running.

## `real_vs_model.csv` and `hour_profile.csv`

OpenEnergy model output from the files above and the bundled prices: by year, the fleet's
metered energy at the day-ahead price and BM cashflow per MW-year of registered capacity
(over the days each unit ran), with the optimiser's day-ahead revenue for a 1-hour and a
2-hour battery (95% each way, £5/MWh wear) on three forecasts; and by year and UTC hour,
the fleet's mean net output per MW running and the 2-hour perfect-foresight plan.

## Known issues

- Units are found by name; a battery whose name and lead party do not say so is missed,
  and the list was checked by hand once (2026-10-31).
- A PN is a position, not what happened: one unit in January 2025 notified 1,262 MWh of
  exports and 443 of imports in a week and metered 615 and 723. Physical operation comes
  from metered output.
- Frequency response and intraday trading are not in these files; the BM cashflows are
  Elexon's indicative values, not final settlement.
