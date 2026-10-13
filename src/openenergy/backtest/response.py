"""Frequency response stacked with trading in the rolling backtest."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd

from openenergy.data.response import SERVICES, ResponseMarket
from openenergy.dispatch.arbitrage import Reserve
from openenergy.errors import ConfigError

FloatArray = npt.NDArray[np.float64]
RESPONSE_FORECASTS = ("previous_day", "actual")
LONDON = "Europe/London"
# Assumed: an EFA day's auction results are public by 15:00 UK time the day before it starts.
RESULTS_HOUR = 15
MAX_HISTORY_DAYS = 7
_DAY = pd.Timedelta(days=1)


@dataclass(frozen=True, eq=False)
class Response:
    """Frequency-response services the battery may sell alongside trading.

    MW for each block are fixed in the plan for the day the block starts in and paid the
    actual clearing price. ``forecast`` sets the price planned on: ``previous_day`` uses the
    latest earlier block at the same time of day whose result was public at the decision
    time; ``actual`` uses the clearing price itself (an upper bound). ``energy_paid`` buys
    and sells the energy delivered at the trading price instead of treating it as free.
    """

    market: ResponseMarket
    forecast: str = "previous_day"
    energy_paid: bool = False

    def __post_init__(self) -> None:
        if self.forecast not in RESPONSE_FORECASTS:
            raise ConfigError(
                f"forecast must be one of {', '.join(RESPONSE_FORECASTS)}, got {self.forecast!r}"
            )


@dataclass(frozen=True)
class DayReserve:
    """A day's reserve options, the actual clearing prices of its blocks and their market rows."""

    reserve: Reserve
    actual: FloatArray
    rows: npt.NDArray[np.int64]


class Stacking:
    """Builds each day's reserve options and carries blocks committed across midnight."""

    def __init__(self, response: Response, lead_hours: float) -> None:
        market = response.market
        self.response = response
        self.lead = pd.Timedelta(hours=lead_hours)
        self.services = tuple(SERVICES[name] for name in market.services)
        self.starts = pd.DatetimeIndex(market.prices.index)
        self.ends = pd.DatetimeIndex(market.prices["end"])
        self.prices = market.prices[market.services].to_numpy(dtype=np.float64)
        self.utilisation = market.utilisation_at(self.starts)[market.services].to_numpy(
            dtype=np.float64
        )
        self.published = _published(self.starts)
        self.row_of = {start: row for row, start in enumerate(self.starts)}
        self.carried: dict[int, FloatArray] = {}

    def positions(self, index: pd.DatetimeIndex) -> npt.NDArray[np.int64]:
        """Market row of the block covering each timestamp, or -1."""
        rows = self.starts.searchsorted(index, side="right") - 1
        inside = (rows >= 0) & (index < self.ends[np.clip(rows, 0, None)])
        return np.where(inside, rows, -1).astype(np.int64)

    def missing(self, day: pd.DatetimeIndex) -> str | None:
        """Why the day cannot be settled, if a block covering it has no clearing price."""
        rows = self.positions(day)
        if (rows < 0).any():
            return "no frequency response blocks"
        if np.isnan(self.prices[np.unique(rows)]).any():
            return "no frequency response clearing price"
        return None

    def day_reserve(self, horizon: pd.DatetimeIndex) -> DayReserve:
        """Options for the horizon; blocks starting before it keep their committed MW."""
        positions = self.positions(horizon)
        rows = np.unique(positions[positions >= 0])
        block = np.searchsorted(rows, positions).astype(np.int64)
        block[positions < 0] = -1
        decision = horizon[0] - self.lead
        actual = self.prices[rows]
        planning = actual if self.response.forecast == "actual" else self._forecast(rows, decision)
        fixed = np.full(actual.shape, np.nan)
        for i, row in enumerate(rows):
            if self.starts[row] < horizon[0]:
                fixed[i] = self.carried.get(int(row), np.zeros(len(self.services)))
        # No market (or no forecast) for a service in a block: nothing can be sold there.
        fixed[np.isnan(planning) & np.isnan(fixed)] = 0.0
        step = horizon[1] - horizon[0] if horizon.size > 1 else pd.Timedelta(hours=1)
        beyond = (self.ends[rows] - (horizon[-1] + step)) / pd.Timedelta(hours=1)
        reserve = Reserve(
            self.services,
            block,
            np.nan_to_num(planning),
            self.utilisation[rows],
            fixed,
            self.response.energy_paid,
            np.clip(np.asarray(beyond, dtype=np.float64), 0.0, None),
        )
        return DayReserve(reserve, np.nan_to_num(actual), rows)

    def commit(self, day: DayReserve, held: FloatArray, day_end: pd.Timestamp) -> None:
        """Remember MW for blocks that start before ``day_end`` and run past it."""
        self.carried = {
            int(row): held[i]
            for i, row in enumerate(day.rows)
            if self.starts[row] < day_end < self.ends[row]
        }

    def _forecast(self, rows: npt.NDArray[np.int64], decision: pd.Timestamp) -> FloatArray:
        planned = np.full((rows.size, len(self.services)), np.nan)
        for i, row in enumerate(rows):
            local = self.starts[row].tz_convert(LONDON).tz_localize(None)
            for back in range(1, MAX_HISTORY_DAYS + 1):
                # Same UK clock time on an earlier day, so clock changes keep the match.
                same_time = (local - back * _DAY).tz_localize(LONDON).tz_convert("UTC")
                earlier = self.row_of.get(same_time, -1)
                if earlier < 0 or self.published[earlier] > decision:
                    continue
                gaps = np.isnan(planned[i])
                planned[i, gaps] = self.prices[earlier, gaps]
                if not np.isnan(planned[i]).any():
                    break
        return planned


def _published(starts: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """When each block's auction result is assumed public."""
    local = starts.tz_convert(LONDON)
    # The EFA day starts at 23:00 UK time; results come out the afternoon before.
    efa_date = (local + pd.Timedelta(hours=1)).normalize().tz_localize(None)
    public = efa_date - _DAY + pd.Timedelta(hours=RESULTS_HOUR)
    return pd.DatetimeIndex(public).tz_localize(LONDON).tz_convert("UTC")
