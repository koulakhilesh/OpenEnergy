from datetime import date

import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError, DataError, InfeasibleDispatchError
from openenergy.assets import BatterySpec
from openenergy.backtest import BacktestConfig, run_backtest
from openenergy.data import PriceSeries
from openenergy.dispatch import DispatchConfig, optimise_dispatch
from openenergy.forecast import NaiveLastWeek, PerfectForesight


def prices(days: int = 10, seed: int = 0) -> PriceSeries:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2019-01-01", periods=days * 24, freq="h", tz="UTC")
    shape = 40 + 20 * np.sin(np.arange(days * 24) * 2 * np.pi / 24)
    return PriceSeries(pd.Series(shape + rng.normal(0, 5, days * 24), index=index), "GBP", "GB")


def battery(**overrides: float) -> BatterySpec:
    params: dict[str, float] = {"power_mw": 1.0, "energy_mwh": 2.0, "initial_soc": 0.5}
    params.update(overrides)
    return BatterySpec(**params)


class RecordingForecaster:
    name = "recording"

    def __init__(self, actual: PriceSeries) -> None:
        self.inner = PerfectForesight(actual)
        self.calls: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    def forecast(self, history: pd.Series, index: pd.DatetimeIndex) -> np.ndarray:
        self.calls.append((history.index.max(), index[0]))
        return self.inner.forecast(history, index)


def test_perfect_foresight_equals_sum_of_daily_optima() -> None:
    actual = prices()
    spec = battery()
    result = run_backtest(spec, actual, PerfectForesight(actual))
    expected = sum(
        optimise_dispatch(spec, spec.initial_state(), actual.day(day), 1.0).expected_revenue
        for day in actual.complete_days()
    )
    assert result.daily["revenue"].sum() == pytest.approx(expected)
    assert result.daily["revenue"].to_numpy() == pytest.approx(
        result.daily["expected_revenue"].to_numpy()
    )


def test_interval_frame_is_consistent() -> None:
    actual = prices(days=3)
    result = run_backtest(battery(), actual, PerfectForesight(actual))
    frame = result.intervals
    assert list(frame.columns) == [
        "price",
        "forecast",
        "charge_mw",
        "discharge_mw",
        "energy_mwh",
        "revenue",
    ]
    assert len(frame) == 72
    revenue = frame["price"] * (frame["discharge_mw"] - frame["charge_mw"])
    assert frame["revenue"].to_numpy() == pytest.approx(revenue.to_numpy())
    assert result.daily["revenue"].sum() == pytest.approx(frame["revenue"].sum())


def test_forecaster_never_sees_prices_after_decision_time() -> None:
    actual = prices()
    forecaster = RecordingForecaster(actual)
    run_backtest(battery(), actual, forecaster, BacktestConfig(lead_hours=12))
    assert forecaster.calls
    for latest_seen, day_start in forecaster.calls[1:]:
        assert latest_seen < day_start - pd.Timedelta(hours=12)


def test_naive_skips_days_without_history_and_settles_at_actual() -> None:
    actual = prices(days=14)
    result = run_backtest(battery(), actual, NaiveLastWeek())
    assert sorted(result.skipped) == [date(2019, 1, d) for d in range(1, 8)]
    assert "history" in result.skipped[date(2019, 1, 1)]
    assert len(result.daily) == 7
    assert not np.allclose(result.daily["revenue"], result.daily["expected_revenue"])


def test_incomplete_day_is_skipped_and_state_carries() -> None:
    actual = prices(days=4)
    raw = actual.prices.copy()
    raw.iloc[30] = np.nan
    gappy = PriceSeries(raw, "GBP", "GB")
    result = run_backtest(battery(), gappy, PerfectForesight(gappy))
    assert date(2019, 1, 2) in result.skipped
    assert "incomplete" in result.skipped[date(2019, 1, 2)]
    assert list(result.daily.index) == [date(2019, 1, 1), date(2019, 1, 3), date(2019, 1, 4)]


def test_days_argument_restricts_simulation() -> None:
    actual = prices()
    days = [date(2019, 1, 3), date(2019, 1, 5)]
    result = run_backtest(battery(), actual, PerfectForesight(actual), days=days)
    assert list(result.daily.index) == days


def test_degradation_reduces_soh_over_time() -> None:
    actual = prices()
    spec = battery(cycle_fade=1e-3, calendar_fade=0.05)
    result = run_backtest(spec, actual, PerfectForesight(actual))
    soh = result.daily["soh"].to_numpy()
    assert (np.diff(soh) < 0).all()
    assert result.final_state.soh == pytest.approx(soh[-1])
    assert result.final_state.equivalent_cycles == pytest.approx(
        result.daily["equivalent_cycles"].iloc[-1]
    )


def test_infeasible_day_reports_date() -> None:
    actual = prices(days=2)
    spec = battery(power_mw=0.01, initial_soc=0.0)
    config = BacktestConfig(dispatch=DispatchConfig(end_soc=1.0))
    with pytest.raises(InfeasibleDispatchError, match="2019-01-01"):
        run_backtest(spec, actual, PerfectForesight(actual), config)


def test_no_days_to_simulate_raises() -> None:
    actual = prices(days=3)
    with pytest.raises(DataError, match="no days"):
        run_backtest(battery(), actual, NaiveLastWeek())


def test_result_metadata() -> None:
    actual = prices(days=2)
    result = run_backtest(battery(), actual, PerfectForesight(actual))
    assert result.forecaster == "perfect_foresight"
    assert result.currency == "GBP"
    assert result.step_hours == 1.0


def test_config_rejects_negative_lead() -> None:
    with pytest.raises(ConfigError, match="lead_hours"):
        BacktestConfig(lead_hours=-1)
