# Real batteries

OpenEnergy's optimiser plans a hypothetical battery. This page checks it against what GB's
real grid batteries did, unit by unit, from Elexon's and NESO's open data (`data/fleet/`,
written by `scripts/fetch_fleet.py` and `scripts/fetch_fleet_response.py` and compared by
`scripts/real_batteries.py`). Try it in the
[web app](https://open-energy-eight.vercel.app/fleet).

## What open data shows about a battery

Elexon publishes, for every Balancing Mechanism (BM) unit:

- its **physical notification** (PN): the position it expects to run at, fixed an hour
  ahead, which reflects every trade it made up to then but not where or at what price;
- its **metered output** (B1610): what the meter recorded each half-hour;
- the **BM actions** NESO took on it after that, with indicative volumes and cashflows.

NESO publishes what it paid each unit for **frequency response**: the auction results by
unit for Dynamic Containment, Regulation and Moderation from September 2021, and for the
response and reserve services that replaced them (Enduring Auction Capability) from
November 2023. The prices of a unit's own trades are not public. So three measures are
reported:

1. **Metered energy at the day-ahead price**: what the unit physically did, valued at the
   GB day-ahead price. It compares directly with OpenEnergy's optimiser, which trades
   physical energy at that price.
2. **Estimated total**: the unit's settlement as the market computes it, with one
   assumption. A unit is paid for its contracted position (taken as its PN, priced here at
   the day-ahead price because its real contract prices are unknown), for its BM actions,
   and for the difference between its meter and both, at the system (imbalance) price.
3. **Response**: the megawatts each unit won in NESO's response auctions, times the hours
   held and the clearing price. Energy delivered while holding response is already in the
   meter, so response adds to the estimated total without counting anything twice.

A PN is not what happened. One unit in the week of 20 January 2025 notified 1,262 MWh of
exports and 443 MWh of imports and metered 615 and 723: it sold ahead and was then
instructed back in the BM. Physical operation here always comes from the meter.

Battery units are found by name in Elexon's register (83 units; "battery", "BESS",
"energy storage"); 78 of them ran between January 2021 and October 2026. Their registered
capacity covers about half of GB's grid batteries by 2025 (REPD): the rest are not BM units
or are not named as batteries. Units with no registered generation capacity use their
demand capacity or metered peak.

## The fleet, year by year

Per MW-year of registered capacity, over the days each unit ran or held response; the model
is a 1 MW battery, 95% each way, £5/MWh wear, on the day-ahead market only:

| Year | Units | MW-years (REPD battery MW) | Full-power hours discharged | Metered energy at day-ahead price | Estimated total | Response | Total with response | Model 1 h: last week's prices / OpenEnergy forecast / perfect | Model 2 h: perfect |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 32 | 970 (2,837) | 306 | £4,134 | £9,523 | £20,093 | £29,616 | £19,776 / £21,092 / £25,394 | £46,440 |
| 2024 | 43 | 1,439 (3,504) | 399 | £4,053 | £16,223 | £7,751 | £23,973 | £15,619 / £17,897 / £21,459 | £39,412 |
| 2025 | 55 | 2,068 (4,220) | 402 | £3,585 | £16,687 | £20,176 | £36,864 | £19,080 / £21,112 / £24,192 | £44,974 |

The estimated total is made of (2025, per MW-year): contracts at the day-ahead price
£17,662, BM actions £10,529 and imbalance −£11,503. Energy out per energy in at the meter
was 82–85%.

2021 and 2022 are in the data but not the table: fewer than 20 units ran, under a quarter
of the fleet, and they metered 67–69% of what they imported, as frequency response held
their charge. Response was most of their income: £49,387 per MW-year in 2022, against an
estimated total of −£1,283 from energy.

What it shows:

- **Real batteries do much less day-ahead arbitrage than the model.** The energy they
  physically moved was worth £3,600–4,100 per MW-year at the day-ahead price, 17–23% of
  what a 1-hour battery planning on OpenEnergy's forecast earns there. They discharge as
  much (about 400 full-power hours a year since 2024) but not only at the day's peaks.
- **The shape is the same, a fifth the size.** In 2025 the fleet charged most at 02:00–03:00
  and 13:00 UTC and exported most at 17:00–18:00 (0.12–0.13 MW per MW running), the hours
  a 2-hour optimiser with perfect foresight uses (0.57–0.64 MW per MW). The fleet's net
  output correlates 0.34–0.42 with the day-ahead price from 2023
  (`data/fleet/hour_profile.csv`).
- **Their money comes from elsewhere.** On the estimate, real batteries made £16,200–16,700
  per MW-year in 2024 and 2025 from energy: 69–76% of what a 1-hour optimiser with perfect
  foresight earns on the day-ahead market, and 79–91% of what it earns on OpenEnergy's
  forecast, through the BM, intraday trading and positions that are bought back.
- **Response is the rest, and it swings.** Frequency response added £20,100 per MW-year in
  2023, £7,800 in 2024, when response prices collapsed as the fleet grew (May 2024 cleared
  at about 5p per MW per hour), and £20,200 in 2025. With it, real batteries made
  £24,000–36,900 per MW-year from 2023 to 2025, 112–152% of what the 1-hour optimiser with
  perfect foresight earns on the day-ahead market alone, and 61–82% of the 2-hour one.

## North and south of the border

| Year | Zone | Units | Estimated total | Response | Total with response | Contracts at day-ahead | BM actions | Imbalance | Metered energy at day-ahead |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024 | Scotland | 8 | £17,132 | £2,371 | £19,503 | £34,136 | £3,571 | −£20,575 | £5,891 |
| 2024 | England and Wales | 35 | £15,977 | £9,205 | £25,182 | £14,570 | £9,672 | −£8,265 | £3,556 |
| 2025 | Scotland | 11 | £17,572 | £21,081 | £38,653 | £43,720 | −£2,808 | −£23,340 | £5,421 |
| 2025 | England and Wales | 44 | £16,490 | £19,974 | £36,464 | £11,836 | £13,510 | −£8,857 | £3,174 |

GBP per MW-year. Transmission-connected units are placed by their transmission loss factor,
which is set by zone. Scottish batteries end up with about the same total by a different
route: they sell far more ahead and are then paid less, or pay, in the BM and imbalance,
where NESO buys power back north of the [B6 boundary](constraints.md#scotland-and-england-wales)
that the lines south cannot carry. They also discharged more (448–490 full-power hours
against 382–386), and their metered energy was worth more at the day-ahead price. A
location's value shows up in how a battery is paid, not (yet) in how much. Response is
bought nationally; Scottish units won little of it in 2024 and as much as the rest in 2025.

## Limits

- Response is valued at the auction clearing price for the megawatts won; payments cut for
  poor delivery are not public and are not subtracted. Response before September 2021 is
  missing, and units that are not BM units are not matched.
- The estimate prices contracts at the day-ahead price; batteries that sold intraday at
  better prices earned more than shown, and the imbalance term absorbs the difference.
- BM cashflows are Elexon's indicative values, not final settlement.
- Battery duration is not registered, so the comparison shows 1-hour and 2-hour models.
- Units are found by name, checked by hand once; a battery named otherwise is missed.

Data: Elexon BMRS (BMRS data licence; contains BMRS data © Elexon Limited copyright and
database right 2026); NESO response auction results by unit (NESO Open Data Licence);
Ember and Elexon prices as bundled. Details in `data/fleet/README.md`.
