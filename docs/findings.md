# Findings

What OpenEnergy's runs show so far, each with the page that has the method, the numbers
and the limits. Every number here comes from a command or script in the repository and
was re-run for v6.0 (v6.1 changed only the web app; v7.0 added real batteries and zones;
v8.0 added response, the evening premium, two zones, the live forecast and the investment
case, and re-ran the saturation study).
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
Mechanism and imbalance, they made an estimated £16,200–16,700 per MW-year from energy;
frequency response, from NESO's auction results by unit, added £7,751 in 2024 and £20,176
in 2025. Scottish batteries end up with about the same energy total as English and
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

On FES 2035 systems made secure to the 3-hour reliability standard over the seven weather
years 2019 to 2025, a battery joining NESO's own fleet earns about a third of what the first
battery would (Falling Behind: £13,595 against £39,421 per MW-year), and each MW of that
fleet replaces 0.13–0.20 MW of firm capacity in the pathways that need it
([Forward scenarios](guides/forward-scenarios.md#how-much-storage-can-gb-use)):

<iframe src="https://open-energy-eight.vercel.app/2035?embed=1" title="How much storage can Britain use?" loading="lazy" style="width:100%;height:900px;border:0"></iframe>

## The model follows the gas crisis, not its evening peaks

With the daily gas price, the cost-based model of GB's plants follows the 2022 gas crisis
with a correlation of 0.81 against actual prices (0.40 with quarterly prices), but its daily
spread stays a fraction of the market's in 2021–2022
([System model](guides/system-model.md#daily-or-quarterly-gas-price)). Fuel prices do
not explain the gap. Supply tightness explains its shape: the gap between real and modelled
prices rises from −£8.9/MWh with over 15 GW of de-rated margin to £108.5 at 2–4 GW, and
the evening is when the margin is thinnest. The market's own scarcity price (loss-of-load
probability times £6,000) is a small part of it and makes the model worse, so no scarcity
price is fitted in
([System model](guides/system-model.md#the-evening-premium-and-supply-tightness)).

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

## Under zonal prices, a Scottish battery would be paid for the boundary

Split into Scotland and England and Wales at NESO's day-ahead SCOTEX limit, the system
model's transfer follows the recorded one (correlation 0.63–0.79) and the boundary is full
in 34–36% of hours in 2024 and 2025, close to what NESO's own data show. When it is full,
Scotland's price falls to what its wind costs; a battery there would earn £16,500–18,900
per MW-year from that alone. Today that value reaches Scottish batteries through the
Balancing Mechanism, not the day-ahead price
([Constraints](guides/constraints.md#a-two-zone-model)).

## Today's revenue would not pay for a battery at US costs

Valued over 15 years at 7%, with the Capacity Market's latest price, a 1 MW / 2 MWh battery
paid every year like GB's real batteries in 2023 to 2025 would be worth building at up to
£101,000–218,000 per MW, far below NREL's US cost of £866,000; the model's gas-crisis years
come closest (£621,519 for 2022). GB build costs are not in open data, so the break-even cost is the answer
([Investment case](guides/investment.md)).

## A live forecast knows less than a backtest

Run each morning on the latest open data, OpenEnergy's forecast has prices that end two to
four days before the day it forecasts, because they are published late. On 2025 that
raises its error from £10.65 to £13.97–14.28/MWh, still well under last week's prices
(£21.81). Its live track record is kept on the
[web app](https://open-energy-eight.vercel.app/live)
([Research](guides/research.md#live-forecast)).

If an embedded page does not load, open the [web app](https://open-energy-eight.vercel.app/).
