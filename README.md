<div align="center">
  <img src="docs/assets/logo.png" alt="OpenEnergy logo" width="80" height="80">

  <h3>OpenEnergy</h3>

  <p>Backtest battery storage against real power-market prices.</p>

  <p>
    <a href="https://koulakhilesh.github.io/OpenEnergy/"><strong>Documentation</strong></a>
    ·
    <a href="https://github.com/koulakhilesh/OpenEnergy/issues">Issues</a>
  </p>

  [![CI](https://github.com/koulakhilesh/OpenEnergy/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/koulakhilesh/OpenEnergy/actions/workflows/ci.yml)
  [![Docs](https://github.com/koulakhilesh/OpenEnergy/actions/workflows/docs.yml/badge.svg?branch=master)](https://koulakhilesh.github.io/OpenEnergy/)
</div>

## What it does

Describe a battery and a forecasting approach in a short YAML file. OpenEnergy plans each
day on the forecast, settles the plan at the prices that actually cleared, and reports
what the battery earned, how hard it worked, and how close it came to perfect foresight.

- **Battery physics**: power and energy ratings, charge/discharge efficiencies, SOC
  window, cycle and calendar ageing.
- **Dispatch**: a daily mixed-integer optimisation solved with HiGHS, optionally planning
  the following days too (`dispatch.lookahead_days`; one day adds 5–15% revenue).
- **Backtesting without lookahead**: forecasts see only data available at the decision
  time; plans settle at actual prices.
- **Forecasters**: perfect foresight, last week's prices, noisy foresight and a
  gradient-boosting model.
- **Renewables**: solar and wind plants from capacity-factor profiles, captured price and
  capture rate by year (`openenergy capture`).
- **Co-located sites**: a plant and a battery behind one grid connection with export and
  import limits and optional support payments, compared with separate connections.
- **System analysis**: net load, ramps and renewable surplus as wind and solar scale,
  storage sizing for the system (`openenergy storage`) and for a site (`openenergy sweep`).
- **Emissions**: net emissions from GB carbon intensity and an optional carbon price that
  steers dispatch, planned without lookahead.
- **GB system model**: CCGT, coal and peaking plant dispatched in merit order (optionally
  with unit commitment) from fleet, fuel and carbon data, checked against 2015–2025 prices
  and fuel use (`openenergy system validate`), with scenarios for renewables, storage,
  fleet and carbon policy (`openenergy system run`); storage uses the optional PyPSA backend.
- **Data**: hourly GB day-ahead prices, demand and wind and solar output for 2015–2020
  and capacity factors for 2015–2019 from Open Power System Data; GB hourly day-ahead
  prices for mid-2016 to October 2026 from Ember; half-hourly GB carbon intensity for
  2018–2025 and generation by fuel for 2015–2025 from NESO; and GB fleet, fuel and carbon
  prices from DESNZ, HMRC, the World Bank and the ECB, are bundled.
  `openenergy data update` downloads the latest prices.

## Quick start

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/koulakhilesh/OpenEnergy.git
cd OpenEnergy
uv sync --extra forecast
uv run openenergy compare examples/gb-2019-{naive,ml,perfect}.yaml
```

```text
scenario         forecast             days       revenue   per MW-yr   capture   cycles
gb-2019-perfect  perfect_foresight     363        19,075      19,180    100.0%      464
gb-2019-ml       gradient_boosting     363        14,086      14,164     73.8%      400
gb-2019-naive    naive_last_week       363        13,918      13,995     73.0%      465
```

A 1 MW / 2 MWh battery trading GB day-ahead prices in 2019 would have earned about £14k
per MW-year planning on last week's prices: 73% of what perfect foresight allows. In the
2022 gas crisis the same battery would have earned about £77k
(`examples/gb-2022-naive.yaml`, on Ember prices).

Run one scenario and write its results to `outputs/<name>/`:

```bash
uv run openenergy run examples/gb-2019-naive.yaml
```

Rebuild GB prices from the plants behind them and compare with what happened:

```bash
uv run openenergy system validate
uv sync --extra system   # PyPSA, needed for scenarios with storage
uv run openenergy system run examples/gb-2019-wind3-storage.yaml
```

See the [documentation](https://koulakhilesh.github.io/OpenEnergy/) for the equations,
every scenario setting and the Python API.

## Development

```bash
uv sync --all-extras --group docs
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
uv run mkdocs serve
```

## Roadmap

**Released**

| Release | Scope |
|---------|-------|
| v2.0 | Battery arbitrage backtesting: physics, ageing, dispatch, forecasters, CLI |
| v2.1 | PV and wind assets, captured price, co-located storage |
| v2.2 | Net load, surplus, storage sizing, emissions |
| v3.0 | GB system dispatch with conventional generation via PyPSA, checked against 2015–2020 |
| v3.1 | Optional unit commitment (start-up costs, minimum stable output) and a start-cost price, re-checked against 2015–2020 without fitting to prices |
| v3.2 | Data to 2025: GB prices from Ember, NESO generation and carbon intensity, DUKES and fuel prices, UK ETS; `openenergy data update`; backcast of the gas crisis and coal exit |
| v3.3 | Multi-day planning horizon (`dispatch.lookahead_days`), and a measured answer on planning under price uncertainty: for day-ahead-only trading a scenario plan equals one forecast, and risk aversion costs revenue |

**Planned**

| Release | Scope |
|---------|-------|
| v3.4 | Charts and reports: `openenergy report` writes an HTML report of dispatch, revenue, price distributions and backcast fit |
| v3.5 | Revenue stacking: GB balancing and frequency-response services alongside day-ahead trading, where open data allows, with stochastic planning where a later market lets the battery react to prices |
| v4.0 | Interactive app on the Python API; forward scenarios from NESO's Future Energy Scenarios; GB zones (Scotland, England and Wales) and interconnectors |

Alongside releases: publish to PyPI, add a `CITATION.cff` with a Zenodo DOI, and keep
versioned docs.

Ideas and bug reports are welcome in [issues](https://github.com/koulakhilesh/OpenEnergy/issues).

## Data

Prices, load and renewable generation come from Open Power System Data:

> Open Power System Data. 2020. Data Package Time series. Version 2020-10-06.
> https://doi.org/10.25832/time_series/2020-10-06. (Primary data from various sources,
> for a complete list see URL).

GB day-ahead prices after September 2020 come from Ember,
[European Wholesale Electricity Price Data](https://ember-energy.org/data/european-wholesale-electricity-price-data/)
(primary sources ENTSO-E and EMR Settlement), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), and are converted from EUR with
European Central Bank reference rates (source: ECB).

GB carbon intensity comes from the National Energy System Operator (NESO) Carbon Intensity
API, https://carbonintensity.org.uk/, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

GB generation by fuel comes from NESO's
[historic generation mix](https://www.neso.energy/data-portal/historic-generation-mix),
licensed under the [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence).
Supported by National Energy SO Open Data.

Fleet capacity and efficiency (DUKES 5.8 and 5.10) and fuel prices (Quarterly Energy
Prices 3.2.1) come from the Department for Energy Security and Net Zero, the 2021 UK ETS
price from the UK ETS Authority's
[carbon price determination](https://www.gov.uk/government/publications/determinations-of-the-uk-ets-carbon-price),
and carbon price support rates from HM Revenue & Customs; they contain public sector
information licensed under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
EU ETS (to 2020) and UK ETS (from 2022) prices come from the World Bank
[Carbon Pricing Dashboard](https://carbonpricingdashboard.worldbank.org/compliance/price)
([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)), converted to GBP with a cross
rate OpenEnergy derives from euro reference rates (source: European Central Bank). Unit
sizes and minimum loads for unit commitment come from the Danish Energy Agency's
[Technology Data catalogue](https://ens.dk/en/analyses-and-statistics/technology-data-generation-electricity-and-district-heating)
([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)), and start-up costs from Kumar
et al., *Power Plant Cycling Costs*, NREL/SR-5500-55433, 2012, Table 1-1
(https://www.osti.gov/biblio/1046269), converted with 2011 ECB rates. All accessed
10 October 2026.

The optional storage backend uses PyPSA (Brown, Hörsch and Schlachtberger, *PyPSA: Python
for Power System Analysis*, Journal of Open Research Software 6(1), 2018,
https://doi.org/10.5334/jors.188).

See [data/time_series](data/time_series/README.md),
[data/prices](data/prices/README.md),
[data/carbon_intensity](data/carbon_intensity/README.md) and
[data/system](data/system/README.md) for sources, changes and known issues. OpenEnergy is
not affiliated with or endorsed by any data provider.

## License

MIT for the code; see [LICENSE.txt](LICENSE.txt). Bundled data keeps its own licence.

## Contact

Akhilesh Koul · [koulakhilesh@gmail.com](mailto:koulakhilesh@gmail.com) ·
[LinkedIn](https://linkedin.com/in/akhilesh-koul)
