<div align="center">
  <img src="https://raw.githubusercontent.com/koulakhilesh/OpenEnergy/main/docs/assets/logo.png" alt="OpenEnergy logo" width="80" height="80">

  <h3>OpenEnergy</h3>

  <p>Backtest battery storage against real power-market prices.</p>

  <p>
    <a href="https://koulakhilesh.github.io/OpenEnergy/"><strong>Documentation</strong></a>
    ·
    <a href="https://github.com/koulakhilesh/OpenEnergy/issues">Issues</a>
  </p>

  [![CI](https://github.com/koulakhilesh/OpenEnergy/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/koulakhilesh/OpenEnergy/actions/workflows/ci.yml)
  [![Docs](https://github.com/koulakhilesh/OpenEnergy/actions/workflows/docs.yml/badge.svg?branch=main)](https://koulakhilesh.github.io/OpenEnergy/)
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
- **Revenue stacking**: GB Dynamic Containment, Moderation and Regulation co-optimised with
  day-ahead trading (`response` in a scenario). Adding Dynamic Containment raised a 2-hour
  battery's revenue by 58–155% a year in 2022–2025 (`examples/gb-2025-stacked.yaml`).
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
- **Forward scenarios**: NESO's Future Energy Scenarios pathways (2025–2035) applied to a
  historic weather year, with GB's ten interconnectors trading at neighbouring markets'
  actual prices up to each link's availability fitted from its flows, and unit commitment
  (`system.fes`, `system.interconnectors: links`, `system.commitment`).
- **Web app**: value a battery on any GB year from 2017 or on a FES pathway's modelled
  prices in the browser at [open-energy-eight.vercel.app](https://open-energy-eight.vercel.app/)
  (`web/`, a React and TypeScript front end on the `openenergy.app` FastAPI JSON API, on
  Vercel).
- **Data**: hourly GB day-ahead prices, demand and wind and solar output for 2015–2020
  and capacity factors for 2015–2019 from Open Power System Data; GB hourly day-ahead
  prices for mid-2016 to October 2026 from Ember; half-hourly GB carbon intensity for
  2018 to October 2026 and generation by fuel for 2015–2025 from NESO; GB frequency-response auction
  prices from September 2021 and monthly response utilisation from NESO; GB imbalance
  prices for 2016 to October 2026 from Elexon; and GB fleet, fuel and carbon prices from DESNZ, HMRC,
  the World Bank and the ECB, are bundled. So are NESO's Future Energy Scenarios tables,
  its interconnector register, daily interconnector flows from Elexon and hourly
  day-ahead prices in the six neighbouring markets from Ember.
  `openenergy data update` downloads the latest prices.
- **Reports**: `openenergy report` turns saved runs, system scenarios, backcasts and sweeps
  into one interactive HTML file of charts and tables (optional `report` extra, plotly).

## Quick start

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/). The bundled data come with the
repository, so clone it:

```bash
git clone https://github.com/koulakhilesh/OpenEnergy.git
cd OpenEnergy
uv sync --extra forecast
uv run openenergy compare examples/gb-2019-{naive,ml,perfect}.yaml
```

The library and command line are also on PyPI (`pip install openenergy`, with extras
`forecast`, `system`, `report` and `app`); the package carries no data, and
`openenergy data update` downloads the latest GB prices.

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

Run one scenario and write its results to `outputs/<name>/`, then chart them:

```bash
uv run openenergy run examples/gb-2019-naive.yaml
uv sync --extra report
uv run openenergy report outputs/gb-2019-naive -o outputs/report.html
```

Rebuild GB prices from the plants behind them and compare with what happened:

```bash
uv run openenergy system validate
uv sync --extra system   # PyPSA, needed for scenarios with storage
uv run openenergy system run examples/gb-2019-wind3-storage.yaml
uv run openenergy system run examples/gb-2035-holistic.yaml   # a FES pathway in 2035
```

Run the web app locally (or use it at
[open-energy-eight.vercel.app](https://open-energy-eight.vercel.app/)):

```bash
npm --prefix web ci && npm --prefix web run build   # the React front end (Node 22+)
uv run uvicorn openenergy.app:app
```

See the [documentation](https://koulakhilesh.github.io/OpenEnergy/) for the equations,
every scenario setting and the Python API.

## Development

```bash
uv sync --all-extras --group docs
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
uv run mkdocs serve
cd web && npm ci && npm run build && npm test && npx playwright install chromium && npm run e2e
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
| v3.4 | Reports: `openenergy report` turns saved runs, system scenarios, backcasts and sweeps into one interactive HTML file; chart functions reusable from Python |
| v3.5 | Revenue stacking: GB Dynamic Containment, Moderation and Regulation co-optimised with day-ahead trading; a measured answer on balancing (imbalance prices are valuable only with a forecast open data does not give) and on stochastic planning (still no value) |
| v4.0 | Forward scenarios from NESO's Future Energy Scenarios on a historic weather year; GB's interconnectors as price-taking links to six neighbouring markets, checked against actual flows 2019–2025; a web app (FastAPI, Vercel) valuing a battery on history or a FES pathway |
| v4.1 | A usable [web app](https://open-energy-eight.vercel.app/): the answer first in plain words, instant results for common batteries, value by year and by FES pathway at a glance, side-by-side comparison with shareable links, explanations next to each term, CSV and scenario downloads, and a JSON API; `CITATION.cff` and PyPI release |
| v4.2 | A more credible model: unit commitment with interconnector links; each link's availability fitted from its actual flows, never from prices; a measured answer on the missing daily spread (the everyday intraday shape, not negative prices); forward scenarios and the app re-run. GB zones were dropped: GB keeps one national wholesale price ([DESNZ, REMA summer update, July 2025](https://www.gov.uk/government/publications/review-of-electricity-market-arrangements-rema-summer-update-2025)) |
| v5.0 | A React and TypeScript front end on an extended JSON API (options, explore, compare, FES table), typed from the OpenAPI schema and tested end to end; interconnector availability by price gap from hourly flows, tested out of sample (an option: it does not beat the flat share); data refreshed to October 2026; versioned docs and a Zenodo DOI |

**Planned**

| Release | Scope |
|---------|-------|
| v5.1 | Model follow-ups: why the modelled 2021–2022 gas-crisis spread is only 27–39% of actual; constraints between Scotland and England and the curtailment they cause; a better day-ahead plan than last week's prices |

Alongside releases: refresh and re-check the bundled data
every release; keep CI and its actions current; revisit stochastic planning if an open,
forecastable market price appears.

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

GB frequency-response clearing prices come from NESO's
[Dynamic Containment, Regulation and Moderation auction results](https://www.neso.energy/data-portal/dynamic-containment-data)
and [EAC auction results](https://www.neso.energy/data-portal/eac-auction-results), and
the energy each service moves is derived from NESO's
[system frequency data](https://www.neso.energy/data-portal/system-frequency-data) with
the delivery envelopes in NESO's Response Services Service Terms; all under the
[NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence),
accessed 13 October 2026. Supported by National Energy SO Open Data.

GB imbalance (system) prices come from Elexon's BMRS, reused under the
[BMRS data licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/).
Contains BMRS data © Elexon Limited copyright and database right 2026.

Forward scenarios use NESO's Future Energy Scenarios 2025 and 2026 Ten Year Outlook
([ES1](https://www.neso.energy/data-portal/future-energy-scenario-electricity-supply-data-table-es1)
and [ED1](https://www.neso.energy/data-portal/fes-electricity-demand-summary-data-table-ed1)
tables) and its
[Interconnector Register](https://www.neso.energy/data-portal/interconnector-register),
under the [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence),
accessed 13 October 2026; supported by National Energy SO Open Data. Interconnector flows
come from Elexon's BMRS (FUELHH), under the same BMRS data licence. Day-ahead prices in
France, the Netherlands, Belgium, Norway, Denmark and Ireland come from Ember's European
Wholesale Electricity Price Data (primary sources ENTSO-E and SEMOpx),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), converted with ECB rates.

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
[data/carbon_intensity](data/carbon_intensity/README.md),
[data/system](data/system/README.md),
[data/fes](data/fes/README.md),
[data/scenarios](data/scenarios/README.md),
[data/app](data/app/README.md),
[data/response](data/response/README.md) and
[data/balancing](data/balancing/README.md) for sources, changes and known issues. OpenEnergy is
not affiliated with or endorsed by any data provider.

## License

The code is MIT licensed; see [LICENSE.txt](LICENSE.txt). The written documentation in
`docs/` (text, tables and findings) is licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Bundled data is not covered by
either and keeps its own licence:

| Folder | Data | Licence |
|---|---|---|
| `data/time_series` | Open Power System Data time series (prices, load, renewables, to 2020) | Terms of the original sources; see the [OPSD package](https://doi.org/10.25832/time_series/2020-10-06) |
| `data/prices` | Ember GB and neighbouring-market day-ahead prices; ECB exchange rates | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); ECB reuse terms |
| `data/carbon_intensity` | NESO Carbon Intensity API | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `data/system` | NESO historic generation mix and Interconnector Register | [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence) |
| `data/system` | DESNZ (DUKES, Quarterly Energy Prices, UK ETS 2021), HMRC | [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) |
| `data/system` | World Bank Carbon Pricing Dashboard; Danish Energy Agency technology data | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `data/system` | NREL Power Plant Cycling Costs (values recorded from the report) | US government-sponsored report |
| `data/system` | Elexon BMRS interconnector flows (daily totals) | [BMRS data licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/) |
| `data/fes` | NESO Future Energy Scenarios tables (unchanged) | [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence) |
| `data/scenarios` | OpenEnergy model output built from the sources above | Attribution of every source used; see its README |
| `data/app` | Precomputed web app results built from the sources above | Attribution of every source used; see its README |
| `data/response` | NESO response auction results and system frequency (derived monthly averages) | [NESO Open Data Licence v1.0](https://www.neso.energy/data-portal/neso-open-licence) |
| `data/balancing` | Elexon BMRS system prices | [BMRS data licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/) |

Reuse of any of these requires the attribution given in the folder's `README.md`.

## Citing

If you use OpenEnergy, please cite it with the details in [CITATION.cff](CITATION.cff)
(GitHub's "Cite this repository" button reads it), and credit the data sources each
result lists. From v5.0.0 each GitHub release is also archived on
[Zenodo](https://zenodo.org/) with a DOI (metadata in `.zenodo.json`); cite the DOI of the
version you used.

## Contact

Akhilesh Koul · [koulakhilesh@gmail.com](mailto:koulakhilesh@gmail.com) ·
[LinkedIn](https://linkedin.com/in/akhilesh-koul)
