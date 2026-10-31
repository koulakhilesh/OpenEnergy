"""A Gymnasium environment for day-ahead battery trading, with the optimiser as a baseline.

Needs the ``rl`` extra (``gymnasium``). Each episode is one day. The agent sees what the
optimiser sees when it plans at noon the day before: the day's 24 forecast prices, the hour
and the energy stored. It never sees the actual price; each hour pays the actual price for
the energy sold (or charges it for the energy bought) less a wear cost per MWh moved.
Ending the day away from the starting energy is settled at the day's mean actual price
(never below zero) plus ``end_penalty`` per MWh, so an agent cannot borrow from tomorrow.

OpenEnergy 6.0 trained PPO (Stable-Baselines3, 0.4 and 3 million steps) on 2021-2023 days
with the fundamentals forecast and tested on 2024-2026: it kept 27-38% of the
perfect-foresight revenue where the optimiser planning on the same forecast kept 78-83%
(see the findings in the docs). The environment is here so others can try to do better
against the same baseline: :func:`optimiser_baseline`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import gymnasium as gym
import numpy as np
import numpy.typing as npt
import pandas as pd

from openenergy.assets.battery import BatterySpec
from openenergy.backtest.engine import known_until
from openenergy.data.series import PriceSeries
from openenergy.dispatch.arbitrage import DispatchConfig, optimise_dispatch
from openenergy.errors import ConfigError, OpenEnergyError
from openenergy.forecast.baseline import Forecaster

FloatArray = npt.NDArray[np.float64]
HOURS = 24
OBSERVATION_SIZE = HOURS + 5
OBSERVATION_LIMIT = 50.0


@dataclass(frozen=True)
class Day:
    """One episode: the forecast made the day before and the prices that cleared."""

    day: date
    forecast: FloatArray
    actual: FloatArray


def episodes(
    prices: PriceSeries,
    forecaster: Forecaster,
    days: Iterable[date],
    lead_hours: float = 12.0,
) -> list[Day]:
    """Forecast each whole hourly day as the backtest would; days without one are left out."""
    series = prices.prices
    out = []
    for day in days:
        start = pd.Timestamp(day, tz="UTC")
        index = pd.date_range(start, periods=HOURS, freq="h")
        actual = series.reindex(index)
        if actual.isna().any():
            continue
        history = series[series.index < known_until(start, lead_hours, "auction")]
        try:
            forecast = np.asarray(forecaster.forecast(history, index), dtype=np.float64)
        except OpenEnergyError:  # not enough history to forecast this day
            continue
        if forecast.shape == (HOURS,) and np.isfinite(forecast).all():
            out.append(Day(day, forecast, np.asarray(actual.to_numpy(), dtype=np.float64)))
    return out


class BatteryTradingEnv(gym.Env[npt.NDArray[np.float32], npt.NDArray[np.float32]]):
    """One day of hourly trading for one battery.

    Action: one number in [-1, 1], the share of rated power to discharge (positive) or
    charge (negative), clipped to what the stored energy allows. Observation (29 values):
    the day's forecast standardised by its mean and spread, this hour's standardised
    forecast, the hour / 23, stored energy / capacity, and the forecast's spread and mean
    in GBP 100s. Reward: GBP earned in the hour less wear. ``reset(options={"day": i})``
    replays day ``i``; otherwise a day is drawn at random.
    """

    metadata = {"render_modes": []}  # noqa: RUF012 - Gymnasium declares it per instance

    def __init__(
        self,
        days: Sequence[Day],
        battery: BatterySpec | None = None,
        wear: float = 5.0,
        end_penalty: float = 20.0,
    ) -> None:
        if not days:
            raise ConfigError("the environment needs at least one day")
        self.days = list(days)
        self.battery = battery or BatterySpec(power_mw=1, energy_mwh=2)
        self.wear = wear
        self.end_penalty = end_penalty
        self.start_energy = self.battery.initial_soc * self.battery.energy_mwh
        self.lower = self.battery.soc_min * self.battery.energy_mwh
        self.upper = self.battery.soc_max * self.battery.energy_mwh
        self.observation_space = gym.spaces.Box(
            -OBSERVATION_LIMIT, OBSERVATION_LIMIT, (OBSERVATION_SIZE,), np.float32
        )
        self.action_space = gym.spaces.Box(-1.0, 1.0, (1,), np.float32)
        self._day = self.days[0]
        self._hour = 0
        self._energy = self.start_energy

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[npt.NDArray[np.float32], dict[str, Any]]:
        super().reset(seed=seed)
        if options is not None and "day" in options:
            self._day = self.days[int(options["day"])]
        else:
            self._day = self.days[int(self.np_random.integers(len(self.days)))]
        self._hour = 0
        self._energy = self.start_energy
        return self._observation(), {"day": self._day.day}

    def step(
        self, action: npt.NDArray[np.float32]
    ) -> tuple[npt.NDArray[np.float32], float, bool, bool, dict[str, Any]]:
        spec = self.battery
        power = float(np.clip(action, -1.0, 1.0)[0]) * spec.power_mw
        if power > 0:  # discharge: what leaves the battery is power / eta
            power = min(power, (self._energy - self.lower) * spec.eta_discharge)
            self._energy -= power / spec.eta_discharge
        else:
            power = -min(-power, (self.upper - self._energy) / spec.eta_charge)
            self._energy += -power * spec.eta_charge
        price = float(self._day.actual[self._hour])
        reward = price * power - self.wear * abs(power)
        self._hour += 1
        done = self._hour == HOURS
        if done:
            gap = abs(self._energy - self.start_energy)
            reward -= gap * (max(float(self._day.actual.mean()), 0.0) + self.end_penalty)
        info = {"power_mw": power, "energy_mwh": self._energy}
        return self._observation(), reward, done, False, info

    def _observation(self) -> npt.NDArray[np.float32]:
        forecast = self._day.forecast
        mean, spread = float(forecast.mean()), float(forecast.std()) + 1.0
        hour = min(self._hour, HOURS - 1)
        scaled = (forecast - mean) / spread
        extra = [scaled[hour], hour / (HOURS - 1), self._energy / self.battery.energy_mwh]
        values = np.concatenate([scaled, extra, [spread / 100, mean / 100]])
        clipped: npt.NDArray[np.float32] = np.clip(
            values, -OBSERVATION_LIMIT, OBSERVATION_LIMIT
        ).astype(np.float32)
        return clipped


def optimiser_baseline(days: Sequence[Day], spec: BatterySpec, wear: float = 5.0) -> FloatArray:
    """GBP per day, net of wear, from the optimiser planning on each day's forecast."""
    config = DispatchConfig(degradation_cost=wear)
    state = spec.initial_state()
    out = []
    for day in days:
        plan = optimise_dispatch(spec, state, day.forecast, 1.0, config)
        net = plan.discharge_mw - plan.charge_mw
        moved = plan.discharge_mw + plan.charge_mw
        out.append(float(day.actual @ net - wear * moved.sum()))
    return np.asarray(out)


def policy_revenue(env: BatteryTradingEnv, act: Any) -> FloatArray:
    """GBP per day (net of wear and the end settlement) from ``act(observation) -> action``."""
    out = []
    for i in range(len(env.days)):
        observation, _ = env.reset(options={"day": i})
        total, done = 0.0, False
        while not done:
            observation, reward, done, _, _ = env.step(np.asarray(act(observation), np.float32))
            total += reward
        out.append(total)
    return np.asarray(out)
