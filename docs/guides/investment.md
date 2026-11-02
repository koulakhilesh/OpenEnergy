# Investment case

Does a GB battery pay for itself? `openenergy invest` values a 1 MW / 2 MWh battery over
its life on each year OpenEnergy has seen or modelled, as if every year of its life paid
like that one. The spread of the cases, not any one of them, is the result.

```bash
uv run openenergy invest [--cost-year 2025] [--cost-scale 1] [--life 15] [--rate 0.07] [--out cases.csv]
```

## What goes in

| Item | Value | Source |
|---|---|---|
| Capital cost | £865,595 per MW (2025 build) | NREL ATB 2024, US utility-scale 2-hour battery, Moderate scenario, $1,069/kW in 2022 dollars, at the ECB's 2022 average rate |
| Fixed O&M | £18,852 per MW-year | NREL ATB 2024, as above |
| Capacity Market | £5,957 per MW-year | NESO register: the latest four-year-ahead auction (2029/30, £27.10/kW-year) times its 2-hour storage de-rating factor (21.98%) |
| Life, discount rate | 15 years, 7% real | Settings (`--life`, `--rate`) |

Revenue cases, per MW-year:

- **Real batteries, energy and response** (2023–2025): what GB's real batteries made from
  energy and frequency response ([Real batteries](real-batteries.md)).
- **Model, day-ahead with OpenEnergy's forecast** (2021–2025): the optimiser's 2-hour
  battery on the day-ahead market, planning on OpenEnergy's forecast.
- **Model, FES 2035 with NESO's battery fleet**: a battery joining each FES pathway's 2035
  fleet on modelled prices with perfect foresight, one case per pathway and weather year
  (five pathways, 2019 to 2025;
  [saturation study](forward-scenarios.md#how-much-storage-can-gb-use)).

The **break-even build cost** is what the battery could cost per MW for its net present
value to be zero: the yearly revenue, plus the Capacity Market, less fixed O&M, over its
life at the discount rate. It does not depend on ATB's capital cost.

## What comes out

At the defaults (`data/invest/cases.csv`):

| Revenue case | Cases | Median revenue (£/MW-year) | Break-even build cost, lowest / median / highest (£/MW) | Positive NPV at ATB's cost |
|---|---:|---:|---:|---:|
| Real batteries, energy and response | 3 | 29,616 | 100,892 / 152,288 / 218,302 | 0 |
| Model, day-ahead with OpenEnergy's forecast | 5 | 39,840 | 191,252 / 245,408 / 621,519 | 0 |
| Model, FES 2035 with NESO's battery fleet | 35 | 14,920 | −81,045 / 18,441 / 165,356 | 0 |

What the table shows:

- **No case pays at ATB's cost.** A battery built for £866,000 per MW would need every year
  to pay like the model's 2022, the gas crisis, and even then earns only a 2.2% real
  return. Real batteries' revenue from 2023 to 2025 would cover a build cost of £101,000 to
  £218,000 per MW.
- **The cost is the open question.** ATB's figures are for US projects; GB's are not in
  open data. With ATB's costs halved (`--cost-scale 0.5`), every day-ahead model year and
  one real year earn their cost back, but only the model's 2021 and 2022, the crisis
  years, clear 7%.
- **The 2035 cases are thinner still.** A battery joining FES's 2035 fleet earns less than
  today's batteries, the [saturation study's](forward-scenarios.md#how-much-storage-can-gb-use)
  point; with fixed O&M at ATB's level some cases do not cover their running costs.

## Limits

- Every year of the life pays like one historic or modelled year; there is no revenue
  trend, no tax and no loss of capacity as the cells age.
- Real revenue leaves out intraday trading and is estimated (see [Real
  batteries](real-batteries.md#limits)); the model cases are day-ahead only, and the 2035
  cases assume perfect foresight.
- A new battery can hold a Capacity Market agreement for many years at the price it
  cleared at; here every year pays the latest four-year-ahead price.

Data: NREL, 2024 Annual Technology Baseline (CC BY 4.0); NESO Capacity Market Register
(NESO Open Data Licence v1.0); ECB reference rates. Details in `data/invest/README.md`.
