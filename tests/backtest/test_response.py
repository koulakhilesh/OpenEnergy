from datetime import date

import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError
from openenergy.assets import BatterySpec
from openenergy.backtest import BacktestConfig, Response, Site, run_backtest
from openenergy.backtest.response import Stacking, _published
from openenergy.data import PriceSeries
from openenergy.data.response import ResponseMarket
from openenergy.dispatch import DispatchConfig, GridConnection
from openenergy.forecast import NaiveLastWeek, PerfectForesight


def prices(days: int = 10) -> PriceSeries:
    index = pd.date_range("2019-01-01", periods=days * 24, freq="h", tz="UTC")
    shape = 40 + 20 * np.sin(np.arange(days * 24) * 2 * np.pi / 24)
    return PriceSeries(pd.Series(shape, index=index), "GBP", "GB")


def market(
    price: float | np.ndarray = 5.0, used: float = 0.0, start: str = "2018-12-31 23:00"
) -> ResponseMarket:
    starts = pd.date_range(start, "2019-01-12", freq="4h", tz="UTC", inclusive="left")
    frame = pd.DataFrame(
        {"end": starts + pd.Timedelta(hours=4), "DCL": price, "DCH": 1.0}, index=starts
    )
    months = pd.DatetimeIndex(["2018-12-01", "2019-01-01"], tz="UTC")
    usage = pd.DataFrame({"DCL": used, "DCH": used}, index=months)
    return ResponseMarket(frame, usage)


def battery() -> BatterySpec:
    return BatterySpec(power_mw=1.0, energy_mwh=2.0, eta_charge=0.95, eta_discharge=0.95)


def test_revenue_is_energy_plus_availability_at_clearing_prices() -> None:
    actual = prices()
    result = run_backtest(
        battery(), actual, PerfectForesight(actual), response=Response(market(), "actual")
    )
    daily = result.daily
    assert daily["revenue"].to_numpy() == pytest.approx(
        (daily["energy_revenue"] + daily["response_revenue"]).to_numpy()
    )
    intervals = result.intervals
    paid = (
        (intervals["dcl_mw"] * 5.0 + intervals["dch_mw"] * 1.0).groupby(intervals.index.date).sum()
    )
    assert daily["response_revenue"].to_numpy() == pytest.approx(paid.to_numpy())
    assert (intervals["dcl_mw"] > 0).any()


def test_response_and_trading_share_power() -> None:
    actual = prices()
    result = run_backtest(battery(), actual, NaiveLastWeek(), response=Response(market(2.0)))
    rows = result.intervals
    assert (rows["discharge_mw"] - rows["charge_mw"] + rows["dcl_mw"]).max() <= 1 + 1e-6
    assert (rows["charge_mw"] - rows["discharge_mw"] + rows["dch_mw"]).max() <= 1 + 1e-6


def test_mw_constant_within_each_block() -> None:
    actual = prices()
    result = run_backtest(battery(), actual, NaiveLastWeek(), response=Response(market(2.0)))
    blocks = result.intervals["dcl_mw"].groupby(
        (result.intervals.index - pd.Timestamp("2018-12-31 23:00", tz="UTC"))
        // pd.Timedelta(hours=4)
    )
    assert (blocks.nunique() == 1).all()


def test_utilisation_energy_reaches_the_battery() -> None:
    actual = prices(days=3)
    with_use = run_backtest(
        battery(),
        actual,
        PerfectForesight(actual),
        response=Response(market(5.0, used=0.1), "actual"),
    )
    without = run_backtest(
        battery(), actual, PerfectForesight(actual), response=Response(market(5.0), "actual")
    )
    assert with_use.final_state.throughput_mwh > without.final_state.throughput_mwh


def test_previous_day_forecast_uses_only_published_results() -> None:
    # Clearing prices step up each day, so the plan's price reveals which day it came from.
    starts = pd.date_range("2018-12-31 23:00", "2019-01-12", freq="4h", tz="UTC", inclusive="left")
    by_day = np.array([float((s - starts[0]).days) for s in starts])
    stacking = Stacking(Response(market(by_day)), lead_hours=12)
    day = pd.date_range("2019-01-05", periods=24, freq="h", tz="UTC")
    options = stacking.day_reserve(day)
    planned = options.reserve.price[:, 0]
    published = _published(stacking.starts[options.rows])
    # Decision at noon on 4 January; 4 January's 23:00 block belongs to the EFA day of the
    # 5th, published at 15:00 on the 4th, so its plan uses an older day.
    assert (published > day[0] - pd.Timedelta(hours=12)).any()
    actual_day = by_day[options.rows]
    # Each block plans on the day before, except 5 January 23:00, whose day-before block
    # (4 January 23:00) was not yet published at the decision time: two days back.
    assert (actual_day - planned).tolist() == pytest.approx([1, 1, 1, 1, 1, 1, 2])


def test_blocks_across_midnight_keep_their_committed_mw() -> None:
    # Blocks at 22:00 UTC run past midnight.
    stacking = Stacking(Response(market(start="2018-12-31 22:00")), lead_hours=12)
    first = pd.date_range("2019-01-05", periods=24, freq="h", tz="UTC")
    options = stacking.day_reserve(first)
    held = np.full(options.reserve.price.shape, 0.4)
    stacking.commit(options, held, first[-1] + pd.Timedelta(hours=1))
    second = stacking.day_reserve(first + pd.Timedelta(days=1))
    assert second.reserve.fixed is not None
    assert second.reserve.fixed[0].tolist() == pytest.approx([0.4, 0.4])
    assert np.isnan(second.reserve.fixed[1:]).all()
    assert second.reserve.beyond_hours is not None
    assert second.reserve.beyond_hours[-1] == pytest.approx(2.0)


def test_days_without_clearing_prices_are_skipped() -> None:
    actual = prices()
    late = market(start="2019-01-04 23:00")
    result = run_backtest(battery(), actual, PerfectForesight(actual), response=Response(late))
    assert set(result.skipped) == {date(2019, 1, d) for d in range(1, 5)}
    assert set(result.skipped.values()) == {"no frequency response blocks"}
    assert min(result.daily.index) == date(2019, 1, 5)


def test_days_with_unpriced_blocks_are_skipped() -> None:
    actual = prices(days=3)
    gappy = market()
    gappy.prices.loc["2019-01-02 07:00", "DCL"] = np.nan
    result = run_backtest(battery(), actual, PerfectForesight(actual), response=Response(gappy))
    assert result.skipped == {date(2019, 1, 2): "no frequency response clearing price"}


def test_lookahead_with_response() -> None:
    actual = prices()
    config = BacktestConfig(dispatch=DispatchConfig(lookahead_days=1))
    result = run_backtest(
        battery(), actual, NaiveLastWeek(), config, response=Response(market(3.0, used=0.05))
    )
    assert result.daily["response_revenue"].sum() > 0


def test_sites_reject_response() -> None:
    actual = prices()
    site = Site(pd.Series(1.0, index=actual.prices.index), GridConnection(1.0))
    with pytest.raises(ConfigError, match="co-located"):
        run_backtest(battery(), actual, NaiveLastWeek(), site=site, response=Response(market()))


def test_response_forecast_is_validated() -> None:
    with pytest.raises(ConfigError, match="forecast must be"):
        Response(market(), "tomorrow")
