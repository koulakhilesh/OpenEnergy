from datetime import date

import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError
from openenergy.assets import BatterySpec
from openenergy.backtest import BacktestConfig, Carbon, Site, run_backtest
from openenergy.backtest.engine import _planning_config
from openenergy.data import PriceSeries
from openenergy.dispatch import DispatchConfig, GridConnection
from openenergy.forecast import NaiveLastWeek, PerfectForesight

PERIODS = 24


def cheap_then_dear(days: int = 4) -> PriceSeries:
    """Flat cheap days alternating with days that are dear just after midnight."""
    index = pd.date_range("2019-01-01", periods=days * PERIODS, freq="h", tz="UTC")
    day = np.arange(index.size) // PERIODS
    hour = np.asarray(index.hour)
    values = np.where((day % 2 == 1) & (hour < 2), 200.0, 20.0)
    return PriceSeries(pd.Series(values, index=index), "GBP", "GB")


def spec() -> BatterySpec:
    return BatterySpec(power_mw=1, energy_mwh=2, eta_charge=0.95, eta_discharge=0.95,
                       initial_soc=0.0)  # fmt: skip


def config(lookahead: int, **dispatch: float) -> BacktestConfig:
    return BacktestConfig(dispatch=DispatchConfig(lookahead_days=lookahead, **dispatch))


class Recording:
    name = "recording"

    def __init__(self, inner: NaiveLastWeek | PerfectForesight) -> None:
        self.inner = inner
        self.calls: list[tuple[pd.Timestamp, pd.DatetimeIndex]] = []

    def forecast(self, history: pd.Series, index: pd.DatetimeIndex) -> np.ndarray:
        self.calls.append((history.index.max(), index))
        return self.inner.forecast(history, index)


def test_lookahead_carries_energy_into_a_dear_day() -> None:
    prices = cheap_then_dear()
    daily = run_backtest(spec(), prices, PerfectForesight(prices), config(0))
    ahead = run_backtest(spec(), prices, PerfectForesight(prices), config(1))
    # Starting empty and returning to empty every day, the dear hours just after midnight
    # cannot be reached; looking a day ahead, the battery charges the evening before.
    assert daily.daily["revenue"].sum() == pytest.approx(0.0, abs=1e-6)
    assert ahead.daily["revenue"].sum() > 300
    first = ahead.daily.iloc[0]
    assert first["revenue"] < 0 and first["energy_mwh"] > 1.9
    assert len(ahead.intervals) == len(prices.prices)


def test_lookahead_forecasts_never_see_prices_after_the_decision_time() -> None:
    index = pd.date_range("2019-01-01", periods=21 * PERIODS, freq="h", tz="UTC")
    prices = PriceSeries(pd.Series(np.arange(index.size, dtype=float), index=index), "GBP", "GB")
    recorder = Recording(NaiveLastWeek())
    cfg = config(3)
    run_backtest(spec(), prices, recorder, cfg)
    assert recorder.calls
    for seen, horizon in recorder.calls:
        decision = horizon[0] - pd.Timedelta(hours=cfg.lead_hours)
        assert pd.isna(seen) or seen < decision
        assert len(horizon) % PERIODS == 0 and len(horizon) <= 4 * PERIODS


def test_horizon_shortens_at_the_end_of_the_data() -> None:
    prices = cheap_then_dear(days=4)
    recorder = Recording(PerfectForesight(prices))
    result = run_backtest(spec(), prices, recorder, config(2))
    assert [len(h) // PERIODS for _, h in recorder.calls] == [3, 3, 2, 1]
    assert result.skipped == {}


def test_cycle_cap_scales_with_the_days_planned() -> None:
    cfg = config(2, max_cycles=1.5)
    assert _planning_config(cfg, 3 * PERIODS, PERIODS).max_cycles == pytest.approx(4.5)
    assert _planning_config(cfg, PERIODS, PERIODS) is cfg.dispatch
    assert _planning_config(config(2), 3 * PERIODS, PERIODS).max_cycles is None
    prices = cheap_then_dear()
    result = run_backtest(spec(), prices, PerfectForesight(prices), config(1, max_cycles=0.25))
    assert (
        result.daily["equivalent_cycles"].diff().fillna(result.daily["equivalent_cycles"]).max()
        <= 0.5 + 1e-6
    )


def test_lookahead_with_a_site_and_a_carbon_price() -> None:
    prices = cheap_then_dear()
    index = prices.prices.index
    site = Site(pd.Series(0.5, index=index), GridConnection(1.0))
    carbon = Carbon(pd.Series(200.0, index=index), price_per_t=10.0, planning="actual")
    result = run_backtest(
        spec(), prices, PerfectForesight(prices), config(1), site=site, carbon=carbon
    )
    assert len(result.daily) == 4
    assert result.intervals["export_mw"].shape == (4 * PERIODS,)
    assert "emissions_t" in result.daily


@pytest.mark.parametrize("value", [-1, 7])
def test_lookahead_validation(value: int) -> None:
    with pytest.raises(ConfigError, match="lookahead_days"):
        DispatchConfig(lookahead_days=value)


def test_days_argument_still_restricts_simulation() -> None:
    prices = cheap_then_dear()
    result = run_backtest(
        spec(), prices, PerfectForesight(prices), config(1), days=[date(2019, 1, 2)]
    )
    assert list(result.daily.index) == [date(2019, 1, 2)]
