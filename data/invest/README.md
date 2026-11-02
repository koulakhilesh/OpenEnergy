# Investment inputs

Written by `scripts/fetch_invest.py` for `openenergy invest`
([Investment case](https://koulakhilesh.github.io/OpenEnergy/guides/investment/)).
OpenEnergy is not affiliated with or endorsed by NESO, NREL or the ECB.

## `capacity_market_auctions.csv` and `capacity_market_storage_derating.csv`

Source: NESO, Capacity Market Register (<https://www.neso.energy/data-portal/capacity-market-register>),
the "Capacity Market Auction Static Data" and "Capacity Market De-Rating Factors" files.
Licence: [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence).
Supported by National Energy SO Open Data.

- `capacity_market_auctions.csv`: each auction with a clearing price: `auction`,
  `clearing_gbp_per_kw_year`, `delivery_year` (from the auction name) and `type` (T-1, T-3,
  T-4 or TR).
- `capacity_market_storage_derating.csv`: the de-rating factor for storage of each duration
  (`duration_hours`) in each auction.

Changes: columns renamed; only storage de-rating factors kept; duration read from the
technology class name.

## `battery_costs.csv`

Source: NREL, 2024 Annual Technology Baseline (<https://atb.nrel.gov/>), the `ATBe` file
from the Open Energy Data Initiative. Licence:
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Utility-scale battery storage,
Moderate scenario, market case, 20-year cost recovery: capital cost (`CAPEX`) and fixed O&M
by duration (2 to 10 hours) and year, in 2022 US dollars per kW, unchanged.
`gbp_per_usd_2022` is the 2022 average of the ECB's daily euro reference rates for sterling
divided by those for the dollar (source: ECB).

## Known issues

- ATB costs are for US projects; GB costs differ. `openenergy invest --cost-scale` scales
  them, and the break-even build cost it reports does not depend on their capital cost.
- A new battery can hold a Capacity Market agreement for many years at the price it
  cleared at; the investment case uses the latest four-year-ahead price every year.
