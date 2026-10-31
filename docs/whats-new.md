# What's new in 6.0

OpenEnergy 6.0 makes the model more accurate, answers a research question, and puts the
battery optimiser in the browser. Three defaults changed, and one bug was fixed that moves
results; this page lists each with what it does to the numbers, measured by re-running
every result in these docs.

## New

- **A day-ahead forecast built on fundamentals** (`forecast: fundamentals`): NESO's
  day-ahead demand forecast, Elexon's day-ahead wind forecast, the daily gas price and
  recent prices, each only as published by the decision time, in a model retrained every
  month. From 2023 it halves the error of last week's prices, and a 1 MW / 2 MWh battery
  planning on it keeps 86–89% of the perfect-foresight revenue instead of 74–81%
  ([Research](guides/research.md#how-good-is-openenergys-forecast)). The forecast for every
  hour since 2019 is bundled (`data/forecasts/`).
- **How much storage can GB use?** `openenergy system saturation` scales each FES 2035
  battery fleet from none to three times FES's figure on a secure system: the first half
  of the fleet takes half or more of a battery's value away, and each MW of FES batteries
  replaces only 0.09–0.16 MW of firm capacity in a cold, still spell
  ([Forward scenarios](guides/forward-scenarios.md#how-much-storage-can-gb-use)).
- **The optimiser in your browser**: the [web app](guides/web-app.md) gains a live home
  page, the Battery Lab (any day, battery and forecast, with the whole year solved in the
  background), Grid replay, the 2035 study and Beat the battery. They run the same daily
  programme in TypeScript on HiGHS compiled to WebAssembly, tested against the Python
  backtest. [Concepts](concepts.md#dispatch) has a widget to drag prices and watch the plan.
- **A reinforcement-learning environment** (`openenergy.rl`, `pip install
  'openenergy[rl]'`): a Gymnasium environment with the optimiser as the baseline. An agent
  trained in the design work kept 27–38% of perfect-foresight revenue where the optimiser
  kept 78–83%, so "forecast, then optimise" stays
  ([Research](guides/research.md#can-reinforcement-learning-do-better)).
- **Data**: the daily System Average Price of gas (ONS), NESO's day-ahead demand forecast
  and Elexon's day-ahead wind forecast, each with issue times (`data/fundamentals/`,
  `openenergy data update --fundamentals`; [Data](data.md#what-is-known-the-day-before)).

## Changed defaults

| Setting | Before | 6.0 | To keep the old behaviour |
|---|---|---|---|
| Gas price in the system model | DESNZ quarterly price paid | Daily System Average Price from 2018 | `system.gas_price: quarterly` |
| What a forecaster knows at the decision time | Prices for hours before it | Every day whose auction had cleared (at noon on D−1, all of D−1) | `information: decision` |
| FES systems | As FES gives them | Least firm capacity added to meet 3 hours' loss of load | `fes.adequacy: as_modelled` |

**Daily gas.** The backcast follows the gas crisis much better: the merit order's error
falls by 31–42% in 2021–2024 and its correlation with actual prices rises from 0.40 to 0.81
in 2022 and from 0.10 to 0.53 in 2024. Before the crisis the change is mixed (the 2019
mean is £4.2 lower, now £4.8 below actual), and the missing daily spread is unchanged
([System model](guides/system-model.md#daily-or-quarterly-gas-price)). FES results and
every system scenario from 2018 change with it.

**Auction information.** Last week's prices, perfect foresight and the gradient-boosting
forecaster never used the previous afternoon's prices, so their results do not change.
The fundamentals forecaster uses them.

**Secure FES systems.** Holistic Transition, Electric Engagement and Hydrogen Evolution
2035 get 6.25–9.25 GW of firm capacity, and their unserved energy falls from 215–715 GWh
to 7–13 GWh. Their mean prices fall from £120–211/MWh to £73–76/MWh, and a battery's
perfect-foresight value on them from 1.8–2.7 times the model's own 2025 to about it or
below ([Forward scenarios](guides/forward-scenarios.md#a-secure-system-first)).

## Fixed: the end-of-day energy target

The daily plan required the battery to end each day with *at least* the energy it began
with. When the last hour was cheap, a plan could end fuller, and the next day's target was
then that fuller level, so the battery kept ratcheting up and holding energy it could have
sold. The plan now ends *exactly* at the target ($E_T = E_{target}$, [Concepts](concepts.md#dispatch)).

The effect depends on how often the last hour is cheap on the forecast:

- Last week's prices: under 0.3% a year (2017: £20,682 to £20,633 per MW-year; 2019:
  £13,936 to £13,943).
- Revenue stacking: up to 2% (2025 with DC, DM and DR, energy unpaid: £89,807 to
  £90,766; with energy at day-ahead prices, £127,976 to £125,634).
- Re-planning every half-hour on imbalance prices, where each re-plan set a new target:
  the result changed sign in three of four years, from losing 6–39% against day-ahead to
  +18%, +17%, +1% and −12% ([Revenue stacking](guides/revenue-stacking.md#balancing)).
- The fundamentals forecast in its design stage: a 2024 capture ratio of 73.7% became
  85.3%.

## The web app

The year form moved from `/` to `/run`; `/result`, `/explore`, `/compare` and
`/scenarios` keep their addresses, so shared links still work. The app offers the
fundamentals forecast for historic years from 2019, and the FES table shows the firm
capacity each pathway needed.

## Numbers re-run

Every table and number in these docs was re-run for 6.0 with the commands and scripts
named next to it. The ones that moved by more than rounding are on the pages linked above;
the [Research](guides/research.md) and [Revenue stacking](guides/revenue-stacking.md)
tables move by under 2% except where noted.
