"""Is planning under price uncertainty worth anything to a day-ahead battery?

Each day is planned at noon the day before and settled at actual GB day-ahead prices
(Ember). Scenarios are last week's prices plus each of the forecaster's daily errors over
the last 28 days. Compared, on the same days with a 1 MW / 2 MWh battery:

- forecast:   one plan on last week's prices (OpenEnergy's default)
- mean:       risk-neutral scenario plan; settlement is linear in price, so this is
              exactly the plan on the scenario mean, i.e. one forecast
- cvar 0.5/1: plans that weight the worst 10% of scenarios half or fully
- lookahead:  one forecast, planned with the next day too (dispatch.lookahead_days: 1)

Revenue is after a GBP 5/MWh wear cost on throughput.

Run: uv run python examples/stochastic_value.py [2019 2022 2024]
"""

import sys
from pathlib import Path

import highspy
import numpy as np
import pandas as pd

from openenergy.assets import BatterySpec
from openenergy.assets.battery import apply_dispatch
from openenergy.data import EmberPriceSource
from openenergy.dispatch import DispatchConfig, optimise_dispatch

DATA = Path(__file__).parents[1] / "data/prices/gb_day_ahead_ember.csv"
SCENARIOS, ALPHA, WEAR = 28, 0.1, 5.0
INF = highspy.kHighsInf
DAY = pd.Timedelta(days=1)


def cvar_plan(spec, energy, scenarios, beta):
    """Maximise (1 - beta) * mean revenue + beta * CVaR of revenue over scenarios."""
    count, n = scenarios.shape
    power = spec.power_mw
    lower, upper = spec.soc_min * spec.energy_mwh, spec.soc_max * spec.energy_mwh
    c, d, e, u, z, y = 0, n, 2 * n, 3 * n + 1, 4 * n + 1, 4 * n + 2
    size = y + count
    mean = scenarios.mean(axis=0)
    cost, low, high = np.zeros(size), np.zeros(size), np.zeros(size)
    cost[c : c + n], cost[d : d + n] = -(1 - beta) * (mean + WEAR), (1 - beta) * (mean - WEAR)
    cost[z], cost[y:] = beta, -beta / (ALPHA * count)
    high[c : c + 2 * n] = power
    low[e : e + n + 1], high[e : e + n + 1] = lower, upper
    low[e] = high[e] = low[e + n] = high[e + n] = energy
    high[u : u + n] = 1
    low[z], high[z], high[y:] = -INF, INF, INF
    rows = []
    for t in range(n):
        rows.append(([e + t + 1, e + t, c + t, d + t],
                     [1, -1, -spec.eta_charge, 1 / spec.eta_discharge], 0, 0))  # fmt: skip
        rows.append(([c + t, u + t], [1, -power], -INF, 0))
        rows.append(([d + t, u + t], [1, power], -INF, power))
    for s, price in enumerate(scenarios):
        # y_s >= z - revenue_s: the shortfall below the value-at-risk z
        columns = [y + s, z, *range(c, c + n), *range(d, d + n)]
        rows.append((columns, [1, -1, *-(price + WEAR), *(price - WEAR)], 0, INF))
    lp = highspy.HighsLp()
    lp.num_col_, lp.num_row_ = size, len(rows)
    lp.sense_ = highspy.ObjSense.kMaximize
    lp.col_cost_, lp.col_lower_, lp.col_upper_ = cost, low, high
    lp.row_lower_ = np.array([r[2] for r in rows], dtype=float)
    lp.row_upper_ = np.array([r[3] for r in rows], dtype=float)
    lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
    lp.a_matrix_.num_col_, lp.a_matrix_.num_row_ = size, len(rows)
    lp.a_matrix_.start_ = np.cumsum([0] + [len(r[0]) for r in rows], dtype=np.int32)
    lp.a_matrix_.index_ = np.array([i for r in rows for i in r[0]], dtype=np.int32)
    lp.a_matrix_.value_ = np.array([v for r in rows for v in r[1]], dtype=float)
    lp.integrality_ = [
        highspy.HighsVarType.kInteger if u <= i < u + n else highspy.HighsVarType.kContinuous
        for i in range(size)
    ]
    solver = highspy.Highs()
    solver.setOptionValue("output_flag", False)
    solver.passModel(lp)
    solver.run()
    x = np.asarray(solver.getSolution().col_value)
    return np.clip(x[c : c + n], 0, power), np.clip(x[d : d + n], 0, power)


def main(years: list[int]) -> None:
    prices = EmberPriceSource(DATA).prices().prices
    spec = BatterySpec(power_mw=1, energy_mwh=2, eta_charge=0.95, eta_discharge=0.95)
    config = DispatchConfig(degradation_cost=WEAR)

    def day(start: pd.Timestamp) -> np.ndarray | None:
        values = prices.loc[start : start + DAY - pd.Timedelta(hours=1)].to_numpy()
        return values if len(values) == 24 and not np.isnan(values).any() else None

    print(f"{'year':<6}{'plan':<12}{'revenue':>10}{'vs forecast':>13}{'loss days':>11}")
    for year in years:
        names = ["forecast", "mean", "cvar 0.5", "cvar 1", "lookahead"]
        revenue = {name: [] for name in names}
        state = dict.fromkeys(names, spec.initial_state())
        for start in pd.date_range(f"{year}-01-01", f"{year}-12-31", tz="UTC"):
            actual, forecast, ahead = day(start), day(start - 7 * DAY), day(start - 6 * DAY)
            if actual is None or forecast is None or ahead is None:
                continue
            decision = start - pd.Timedelta(hours=12)
            errors = []
            for back in range(1, 60):
                past = decision.normalize() - back * DAY
                if past + DAY > decision:
                    continue
                observed, predicted = day(past), day(past - 7 * DAY)
                if observed is not None and predicted is not None:
                    errors.append(observed - predicted)
                if len(errors) == SCENARIOS:
                    break
            scenarios = forecast + np.array(errors)
            for name in names:
                energy = state[name].energy_mwh
                if name == "forecast":
                    plan = optimise_dispatch(spec, state[name], forecast, 1.0, config)
                    charge, discharge = plan.charge_mw, plan.discharge_mw
                elif name == "lookahead":
                    both = np.concatenate([forecast, ahead])
                    plan = optimise_dispatch(spec, state[name], both, 1.0, config)
                    charge, discharge = plan.charge_mw[:24], plan.discharge_mw[:24]
                else:
                    beta = {"mean": 0.0, "cvar 0.5": 0.5, "cvar 1": 1.0}[name]
                    charge, discharge = cvar_plan(spec, energy, scenarios, beta)
                state[name] = apply_dispatch(spec, state[name], charge, discharge, 1.0).state
                net = actual @ (discharge - charge) - WEAR * (charge + discharge).sum()
                revenue[name].append(float(net))
        base = sum(revenue["forecast"])
        for name in names:
            total = sum(revenue[name])
            losses = sum(value < 0 for value in revenue[name])
            print(f"{year:<6}{name:<12}{total:>10,.0f}{total / base - 1:>13.1%}{losses:>11}")


if __name__ == "__main__":
    main([int(arg) for arg in sys.argv[1:]] or [2019, 2022, 2024])
