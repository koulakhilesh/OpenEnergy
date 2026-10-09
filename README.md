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
- **Dispatch**: a daily mixed-integer optimisation solved with HiGHS.
- **Backtesting without lookahead**: forecasts see only data available at the decision
  time; plans settle at actual prices.
- **Forecasters**: perfect foresight, last week's prices, noisy foresight and a
  gradient-boosting model.
- **Renewables**: solar and wind plants from capacity-factor profiles, captured price and
  capture rate by year (`openenergy capture`).
- **Co-located sites**: a plant and a battery behind one grid connection with export and
  import limits and optional support payments, compared with separate connections.
- **Data**: hourly GB day-ahead prices for 2015–2020 and solar and wind capacity factors
  for 2015–2019 from Open Power System Data are bundled.

## Quick start

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/koulakhilesh/OpenEnergy.git
cd OpenEnergy
uv sync --extra forecast
uv run openenergy compare examples/*.yaml
```

```text
scenario         forecast             days       revenue   per MW-yr   capture   cycles
gb-2019-perfect  perfect_foresight     363        19,075      19,180    100.0%      464
gb-2019-ml       gradient_boosting     363        14,086      14,164     73.8%      400
gb-2019-naive    naive_last_week       363        13,918      13,995     73.0%      465
```

A 1 MW / 2 MWh battery trading GB day-ahead prices in 2019 would have earned about £14k
per MW-year planning on last week's prices: 73% of what perfect foresight allows.

Run one scenario and write its results to `outputs/<name>/`:

```bash
uv run openenergy run examples/gb-2019-naive.yaml
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

| Release | Scope |
|---------|-------|
| v2.0 | Battery arbitrage backtesting |
| v2.1 | PV and wind assets, captured price, co-located storage |
| v2.2 | Net load, curtailment, storage sizing, emissions |
| v3.0 | System dispatch with conventional generation via PyPSA |

Ideas and bug reports are welcome in [issues](https://github.com/koulakhilesh/OpenEnergy/issues).

## Data

The bundled prices come from Open Power System Data:

> Open Power System Data. 2020. Data Package Time series. Version 2020-10-06.
> https://doi.org/10.25832/time_series/2020-10-06. (Primary data from various sources,
> for a complete list see URL).

## License

MIT. See [LICENSE.txt](LICENSE.txt).

## Contact

Akhilesh Koul · [koulakhilesh@gmail.com](mailto:koulakhilesh@gmail.com) ·
[LinkedIn](https://linkedin.com/in/akhilesh-koul)
