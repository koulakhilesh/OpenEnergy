# Revenue stacking

A GB battery can sell more than day-ahead trading. OpenEnergy v3.5 adds the frequency
response services NESO buys every day, co-optimised with trading in the same plan, and
measures what the imbalance (balancing) price is worth with the information open data
gives.

## Frequency response

NESO buys three dynamic response services, each in a low direction (export when
frequency falls) and a high direction (import when it rises), by day-ahead auction in
four-hour EFA blocks:

| Service | Codes | Responds | Energy held |
|---|---|---|---|
| Dynamic Containment | `DCL`, `DCH` | mostly beyond ±0.2 Hz, after a fault | 15 minutes |
| Dynamic Moderation | `DML`, `DMH` | mostly beyond ±0.1 Hz | 30 minutes |
| Dynamic Regulation | `DRL`, `DRH` | continuously beyond ±0.015 Hz | 60 minutes |

Add a `response` section to a battery scenario
([reference](scenarios.md#response)):

```yaml
response:
  path: ../data/response/gb_dynamic_response.csv
  services: [DCL, DCH]
```

```bash
uv run openenergy run examples/gb-2025-stacked.yaml
```

### How it is modelled

Each day is planned at the usual decision time (noon the day before) as one optimisation
over trading and response:

- **MW per block.** For every block and service the plan chooses MW held, constant across
  the block. Blocks that run past midnight are fixed by the day they start in and carried
  into the next day's plan.
- **Power.** MW held for low services plus net discharge cannot exceed the power rating;
  likewise for high services and net charge. MW contracted in each direction is at most
  the power rating.
- **Energy.** The battery keeps enough stored energy (or room) to deliver each service for
  its full duration at every point in the block, and, for a block that runs past the
  horizon, to stay idle until it ends.
- **Utilisation.** Responding moves energy. OpenEnergy uses the monthly average delivery
  per MW from NESO's one-second frequency data and the service delivery envelopes (DC
  about 0.007, DM 0.03–0.04, DR 0.13–0.14 MWh per MW per hour in 2024–2025). That energy
  changes the stored energy, counts towards cycles, ageing and the wear cost, and by
  default is **unpaid**: under NESO's ABSVD adjustment a balancing-mechanism battery is
  neither charged for energy it imports in high services nor paid for energy it exports
  in low services (NESO, *Dynamic Response A18 Submission Document*, 2025).
  `energy: day_ahead` buys and sells it at the trading price instead.
- **Prices.** MW held is paid the actual clearing price (GBP per MW per hour). The plan
  uses `forecast: previous_day`: the latest earlier block at the same UK clock time whose
  auction result was public at the decision time (results are assumed public at 15:00 UK
  time the day before the EFA day). `actual` plans on the clearing price
  itself, an upper bound, and is what the perfect-foresight benchmark uses.

Left out, and stated in `summary.json`: the battery is a price-taker whose offers are
always accepted at the clearing price; it is always available and never penalised for
performance; delivery follows the monthly average rather than the frequency on the day;
reserve products (balancing, quick and slow reserve) and the Balancing Mechanism are not
modelled.

### Results

`examples/gb-2025-stacked.yaml` for each year and service set (1 MW / 2 MWh, 95% each
way, last week's day-ahead prices, £5/MWh wear cost in the plan); revenue per MW-year
before wear cost, as `openenergy run` reports it:

| Year | Day-ahead only | + DC | + DC, DM | + DC, DM, DR |
|---|---:|---:|---:|---:|
| 2022 | 76,940 | 195,927 | 217,004 | 395,148 |
| 2023 | 35,964 | 61,907 | 72,391 | 112,437 |
| 2024 | 28,677 | 45,232 | 47,437 | 51,210 |
| 2025 | 35,861 | 63,872 | 75,766 | 89,807 |

With utilisation energy bought and sold at the day-ahead price (`energy: day_ahead`):

| Year | + DC | + DC, DM | + DC, DM, DR |
|---|---:|---:|---:|
| 2022 | 197,160 | 202,931 | 267,469 |
| 2023 | 61,787 | 68,775 | 112,425 |
| 2024 | 45,032 | 56,820 | 79,949 |
| 2025 | 63,788 | 83,106 | 127,976 |

DM and DR start on 26 March 2022, so their 2022 columns cover 281 days, scaled to a year.

What this shows:

- **Dynamic Containment is the robust gain.** Adding DC raises revenue by 58–155% every
  year, and the answer barely moves with how utilisation energy is settled (DC is rarely
  called). DC availability is 60–78% of the stacked revenue.
- **The battery works less for more.** With DC, equivalent cycles fall from 569–661 a year
  to 319–389: holding power for DC pays more than the marginal arbitrage it displaces.
- **DM and DR depend on an assumption.** DR moves 0.13–0.14 MWh per MW per hour, so who
  pays for that energy decides its value: in 2024 adding DR to DC and DM adds 8% when the
  energy is free and 41% when it is bought and sold at the day-ahead price. The default
  (free) follows NESO's ABSVD treatment of balancing-mechanism units; NESO's 2025 A18
  document describes non-BM units as exposed to imbalance prices on it instead, and
  proposes to extend ABSVD to them.
- **Thin markets.** DR low cleared a median 9 MW per block in 2022 and about 480 MW in
  2025, against about 1,100–1,250 MW of DC; a price-taker result for one small battery
  says nothing about what a fleet entering these markets would earn.
- **Prices fell, then partly recovered.** DC low cleared at £19.20/MW/h on average in
  2022 and £2.25 in 2024, then £3.93 in 2025 (see `data/response/README.md`).

## Balancing

GB's imbalance price (the system price, one per half-hour since 2015) settles any
difference between a battery's contracted position and what it delivers. It is the
obvious "later market": a battery could take a day-ahead position and then deviate when
the imbalance price looks better.
[`examples/imbalance_value.py`](https://github.com/koulakhilesh/OpenEnergy/blob/master/examples/imbalance_value.py)
tests this on Elexon's system prices, 2016–2025 (`data/balancing/`), after a £5/MWh wear
cost:

| Year | Days | Follow day-ahead | Perfect imbalance foresight | Re-plan each half-hour (t−2 price) | Re-plan on known day-ahead | Imbalance only |
|---|---:|---:|---:|---:|---:|---:|
| 2019 | 355 | 4,417 | 52,791 | 2,682 | 9,152 | −2,169 |
| 2022 | 361 | 64,267 | 324,412 | 60,243 | 82,276 | 22,555 |
| 2024 | 366 | 17,633 | 94,200 | 12,579 | 23,390 | 5,223 |
| 2025 | 365 | 24,693 | 103,850 | 15,916 | 30,993 | 6,018 |

Days with a missing price in either market are left out.

What this shows:

- **The upside is large.** Knowing the day's imbalance prices would earn 4–12 times the
  day-ahead revenue: the price is far more volatile than day-ahead.
- **A simple real-time strategy loses money.** Re-planning before each half-hour on the
  latest published price (two periods back) earns 6–39% less than just delivering the
  day-ahead position, and trading imbalance alone on the same information earns at most 35%
  of day-ahead, and lost money in 2019. The value is all in forecasting the
  imbalance price, which open data does not give.
- **Re-planning on known day-ahead prices gains 25–107%**, but that is the value of knowing
  the day-ahead price (a battery bidding a curve into the auction captures much of it), not
  of balancing.

So OpenEnergy does not offer a balancing mode: with the information available, it would
mislead.

## Planning under uncertainty

v3.3 showed that for day-ahead trading a plan over price scenarios equals a plan on their
mean. The same holds for frequency response: MW is committed before the auction clears
and paid the clearing price, so revenue is linear in price and the value of a stochastic
solution is zero. Balancing is the one market with a genuine later decision, and above it
pays only with a forecast that open data does not support. Stochastic planning therefore
stays out of OpenEnergy until a later market with an open, forecastable price is added.

## Sources

Frequency response: NESO, Dynamic Containment, Regulation and Moderation auction results
and EAC auction results; utilisation from NESO system frequency data with the delivery
envelopes of NESO's Response Services Service Terms (version 6); ABSVD treatment from
NESO's Dynamic Response A18 Submission Document (2025). NESO Open Data Licence v1.0;
supported by National Energy SO Open Data. Imbalance prices: Elexon BMRS; contains BMRS
data © Elexon Limited copyright and database right 2026. Details and known issues in
[Data](../data.md).
