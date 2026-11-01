# Findings

What OpenEnergy's runs show so far, each with the page that has the method, the numbers
and the limits. Every number here comes from a command or script in the repository and
was re-run for v6.0 (v6.1 changed only the web app; v7.0 added real batteries and zones).
The headline tables are checked against their source files on every test run
(`tests/test_docs_numbers.py`).

## A battery on GB day-ahead prices

A 1 MW / 2 MWh battery planning on last week's prices earned £13,943 per MW-year in 2019,
£76,948 in the 2022 gas crisis and £35,861 in 2025, keeping 71–83% of what perfect
foresight allows every year from 2017 ([Home](index.md)). Try any day:

<iframe src="https://open-energy-eight.vercel.app/?embed=1&day=2025-01-21&hour=16" title="OpenEnergy simulator" loading="lazy" style="width:100%;height:760px;border:0"></iframe>

## Real batteries trade the same shape, far less of it

GB's real grid batteries, from Elexon's metered data, discharged about 400 full-power hours
a year in 2024 and 2025, at the same hours a day-ahead optimiser uses, but the energy they
moved was worth only 17–23% of what a 1-hour optimiser on OpenEnergy's forecast earns at
the day-ahead price. With their contracts priced at the day-ahead price, the Balancing
Mechanism and imbalance, they made an estimated £16,200–16,700 per MW-year, before
frequency response. Scottish batteries end up with about the same total as English and
Welsh ones, paid more for selling ahead and less in the BM
([Real batteries](guides/real-batteries.md)).

## A better forecast pays, less than its error suggests

OpenEnergy's day-ahead forecast (demand and wind forecasts, the daily gas price and recent
prices, as known the day before) halves the error of last week's prices from 2023 and
keeps 86–89% of perfect-foresight revenue instead of 74–81%. In 2021, when gas prices
rose faster than any model trained on earlier years could follow, last week's prices did
better ([Research](guides/research.md#how-good-is-openenergys-forecast)). A
reinforcement-learning agent given the same information kept 27–38%
([Research](guides/research.md#can-reinforcement-learning-do-better)).

## Storage saturates, and does little for a cold, still week

On FES 2035 systems made secure to the 3-hour reliability standard, a battery joining
NESO's own fleet earns about a third of what the first battery would (Falling Behind:
£15,551 against £43,609 per MW-year), and each MW of that fleet replaces 0.09–0.16 MW of
firm capacity in the pathways that need it
([Forward scenarios](guides/forward-scenarios.md#how-much-storage-can-gb-use)):

<iframe src="https://open-energy-eight.vercel.app/2035?embed=1" title="How much storage can Britain use?" loading="lazy" style="width:100%;height:900px;border:0"></iframe>

## The model follows the gas crisis, not its evening peaks

With the daily gas price, the cost-based model of GB's plants follows the 2022 gas crisis
with a correlation of 0.81 against actual prices (0.40 with quarterly prices), but its daily
spread stays a fraction of the market's in 2021–2022
([System model](guides/system-model.md#daily-or-quarterly-gas-price)). Fuel prices do
not explain the gap; scarcity pricing and bidding above cost, which open data does not
describe, are left out rather than fitted.

## Frequency response, then arbitrage

Selling Dynamic Containment alongside day-ahead trading raised a 2-hour battery's revenue
by 58–156% a year in 2022–2025, with fewer cycles. Re-planning against imbalance prices
without a forecast of them gained in some years and lost in others
([Revenue stacking](guides/revenue-stacking.md)).

## Constraints are growing, outside the day-ahead price

NESO's thermal constraint costs rose from £1.1 billion in 2021/22 to £2.0 billion in
2025/26, and six boundary groups were at their day-ahead limit a third to a half of the
time from 2024 ([Constraints](guides/constraints.md)). GB's price is national, so this
changes balancing costs, not the day-ahead values above.

If an embedded page does not load, open the [web app](https://open-energy-eight.vercel.app/).
