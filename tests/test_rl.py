from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("gymnasium")
from gymnasium.utils.env_checker import check_env

from openenergy.assets import BatterySpec
from openenergy.data.ember import gb_prices
from openenergy.dispatch import DispatchConfig, optimise_dispatch
from openenergy.errors import ConfigError
from openenergy.forecast import NaiveLastWeek, PerfectForesight
from openenergy.rl import (
    BatteryTradingEnv,
    episodes,
    optimiser_baseline,
    policy_revenue,
)

ROOT = Path(__file__).parents[1]
SPEC = BatterySpec(power_mw=1, energy_mwh=2)
DAYS = [date(2024, 3, 1) + timedelta(days=i) for i in range(10)]


def prices():  # type: ignore[no-untyped-def]
    return gb_prices(
        [ROOT / "data/prices/gb_day_ahead_ember.csv"], date(2024, 2, 1), date(2024, 3, 31)
    )[0]


def test_environment_follows_the_gymnasium_api() -> None:
    env = BatteryTradingEnv(episodes(prices(), NaiveLastWeek(), DAYS), SPEC)
    check_env(env, skip_render_check=True)
    observation, info = env.reset(seed=1, options={"day": 0})
    assert observation.shape == (29,) and info["day"] == DAYS[0]
    with pytest.raises(ConfigError, match="at least one day"):
        BatteryTradingEnv([], SPEC)


def test_replaying_the_optimiser_plan_earns_the_baseline() -> None:
    days = episodes(prices(), NaiveLastWeek(), DAYS)
    assert [d.day for d in days] == DAYS
    env = BatteryTradingEnv(days, SPEC, wear=5.0)
    config = DispatchConfig(degradation_cost=5.0)
    plans = [optimise_dispatch(SPEC, SPEC.initial_state(), d.forecast, 1.0, config) for d in days]
    step = {"day": 0, "hour": 0}

    def replay(_observation: object) -> list[float]:
        plan = plans[step["day"]]
        action = (plan.discharge_mw[step["hour"]] - plan.charge_mw[step["hour"]]) / SPEC.power_mw
        step["hour"] += 1
        if step["hour"] == 24:
            step["day"], step["hour"] = step["day"] + 1, 0
        return [action]

    # Actions are float32, so a replayed plan matches to about a penny a day.
    assert policy_revenue(env, replay) == pytest.approx(optimiser_baseline(days, SPEC), abs=0.01)


def test_perfect_foresight_bounds_the_forecast_and_idling_earns_nothing() -> None:
    series = prices()
    perfect = optimiser_baseline(episodes(series, PerfectForesight(series), DAYS), SPEC)
    naive = optimiser_baseline(episodes(series, NaiveLastWeek(), DAYS), SPEC)
    assert perfect.sum() >= naive.sum()
    env = BatteryTradingEnv(episodes(series, NaiveLastWeek(), DAYS), SPEC)
    assert policy_revenue(env, lambda _o: [0.0]) == pytest.approx(np.zeros(len(DAYS)))
    # Draining the battery is settled at the end of the day, not free.
    drained = policy_revenue(env, lambda _o: [1.0])
    assert (drained < perfect).all()
