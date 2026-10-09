# OpenEnergy

OpenEnergy backtests battery storage and renewable plants against real day-ahead power
prices. You describe the assets and a forecasting approach in a short YAML file;
OpenEnergy plans each day on the forecast, settles the plan at the prices that actually
cleared, and tells you what the site earned, how hard the battery worked, and how close it
came to a perfect-foresight benchmark.

It is built for research questions such as:

- How much is a 2-hour battery worth in the GB day-ahead market?
- How much revenue does a better price forecast buy?
- How much of the average price do solar and wind actually capture?
- Can a battery share a solar farm's grid connection without losing money?
- As wind and solar grow, how much surplus appears, and how much storage absorbs it?
- What do storage and renewables do to emissions, and what does a carbon price change?

## Quick start

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

A 1 MW / 2 MWh battery trading GB day-ahead prices in 2019 would have earned about
£14k per MW-year planning on last week's prices, or 73% of what perfect foresight allows.

Renewables are one command away:

```bash
uv run openenergy capture data/time_series/time_series_60min_singleindex_filtered.csv -t solar
```

GB solar captured 94–106% of the average day-ahead price each year from 2015 to 2019, and
adding a 5 MW battery behind an existing 10 MW solar connection cost almost nothing in
lost trading (see [Research](guides/research.md)).

The whole system is one command too:

```bash
uv run openenergy netload data/time_series/time_series_60min_singleindex_filtered.csv \
  --scale-wind 3 --scale-solar 3 --must-run 8000
```

Tripling 2019 wind and solar would leave 14 TWh of surplus above an 8 GW must-run floor;
a 10 GW / 24 h storage fleet absorbs about three-quarters of it
(see [System analysis](guides/system.md)).

## What it does

1. **Loads prices, capacity factors, demand and carbon intensity** from the bundled
   [Open Power System Data and NESO](data.md) extracts and checks them: UTC timestamps, a
   regular grid, reported gaps and filtered telemetry glitches.
2. **Forecasts** each day using only data available at the decision time (noon the day
   before by default).
3. **Plans** the day with a mixed-integer optimisation that respects power and energy
   limits, efficiencies, an end-of-day state of charge and, for co-located sites, a shared
   grid connection; an optional carbon price steers dispatch.
4. **Settles** the plan at actual prices through the battery physics, including cycle and
   calendar ageing.
5. **Reports** revenue, cycles, state of health, forecast error, the capture ratio against
   perfect foresight, net emissions and, for sites, curtailment, the plant's captured
   price and the value of co-location against separate connections.
6. **Analyses the system**: net load, ramps and surplus as renewables scale, and the
   storage needed to absorb that surplus; `openenergy sweep` sizes storage for a site.

See [Concepts](concepts.md) for the equations and [Scenarios](guides/scenarios.md) for
every setting.

## Roadmap

| Release | Scope |
|---------|-------|
| v2.0 | Battery arbitrage backtesting |
| v2.1 | PV and wind assets, captured price, co-located storage |
| v2.2 | Net load, surplus, storage sizing, emissions (this release) |
| v3.0 | System dispatch with conventional generation via PyPSA |
