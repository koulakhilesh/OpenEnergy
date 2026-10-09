# OpenEnergy

OpenEnergy backtests battery storage against real day-ahead power prices. You describe a
battery and a forecasting approach in a short YAML file; OpenEnergy plans each day on the
forecast, settles the plan at the prices that actually cleared, and tells you what the
battery earned, how hard it worked, and how close it came to a perfect-foresight benchmark.

It is built for research questions such as:

- How much is a 2-hour battery worth in the GB day-ahead market?
- How much revenue does a better price forecast buy?
- What does a degradation cost do to cycling and earnings?

## Quick start

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

A 1 MW / 2 MWh battery trading GB day-ahead prices in 2019 would have earned about
£14k per MW-year planning on last week's prices, or 73% of what perfect foresight allows.

## What it does

1. **Loads prices** from the bundled [Open Power System Data](data.md) extract and checks
   them: UTC timestamps, a regular grid, and reported gaps.
2. **Forecasts** each day using only data available at the decision time (noon the day
   before by default).
3. **Plans** the day with a mixed-integer optimisation that respects power and energy
   limits, efficiencies and an end-of-day state of charge.
4. **Settles** the plan at actual prices through the battery physics, including cycle and
   calendar ageing.
5. **Reports** revenue, revenue per MW-year, captured spread, cycles, state of health,
   forecast error and the capture ratio against perfect foresight.

See [Concepts](concepts.md) for the equations and [Scenarios](guides/scenarios.md) for
every setting.

## Roadmap

| Release | Scope |
|---------|-------|
| v2.0 | Battery arbitrage backtesting (this release) |
| v2.1 | PV and wind assets, captured price, co-located storage |
| v2.2 | Net load, curtailment, storage sizing, emissions |
| v3.0 | System dispatch with conventional generation via PyPSA |
