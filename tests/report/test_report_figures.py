import numpy as np
import pandas as pd
import pytest

from openenergy.report import figures

HOURS = pd.date_range("2019-01-01", periods=48 * 2, freq="h", tz="UTC")


def intervals() -> pd.DataFrame:
    hour = np.asarray(HOURS.hour)
    return pd.DataFrame(
        {
            "price": 40.0 + hour,
            "forecast": 42.0 + hour,
            "charge_mw": np.where(hour < 4, 1.0, 0.0),
            "discharge_mw": np.where(hour >= 18, 0.5, 0.0),
            "energy_mwh": np.linspace(0, 2, HOURS.size),
        },
        index=HOURS,
    )


def daily() -> pd.Series:
    index = pd.date_range("2019-01-30", periods=4, freq="D")
    return pd.Series([1.0, 2.0, 3.0, 4.0], index=index)


def test_revenue_charts() -> None:
    fig = figures.cumulative_revenue({"run": daily(), "benchmark": daily() * 2}, "GBP")
    assert [t.name for t in fig.data] == ["run", "benchmark"]
    assert list(fig.data[1].y) == [2.0, 6.0, 12.0, 20.0]
    monthly = figures.monthly_revenue(daily())
    assert list(monthly.data[0].x) == ["2019-01", "2019-02"]
    assert list(monthly.data[0].y) == [3.0, 7.0]


def test_battery_operation_charts() -> None:
    frame = intervals()
    day = figures.typical_day(frame)
    discharge, charge = day.data
    assert discharge.y[18] == pytest.approx(0.5) and charge.y[0] == pytest.approx(-1.0)
    heat = figures.state_of_charge(frame)
    assert np.asarray(heat.data[0].z).shape == (4, 24)
    assert len(figures.price_and_forecast(frame).data) == 2
    error = figures.forecast_error_by_hour(frame)
    assert list(error.data[0].y) == pytest.approx([2.0] * 24)


def test_revenue_by_market_chart() -> None:
    frame = pd.DataFrame(
        {"energy_revenue": [10.0, 5.0], "response_revenue": [3.0, 4.0]},
        index=pd.date_range("2019-01-31", periods=2, freq="D"),
    )
    fig = figures.revenue_by_market(frame)
    assert [t.name for t in fig.data] == ["trading", "frequency response"]
    assert list(fig.data[1].y) == [3.0, 4.0]


def test_site_and_emission_charts() -> None:
    frame = pd.DataFrame(
        {"available_mwh": [10.0, 20.0], "curtailed_mwh": [1.0, 0.0]},
        index=pd.date_range("2019-01-31", periods=2, freq="D"),
    )
    site = figures.site_by_month(frame)
    assert list(site.data[0].x) == ["2019-01", "2019-02"]
    emissions = figures.cumulative_emissions(pd.Series([-1.0, -2.0], index=frame.index))
    assert list(emissions.data[0].y) == [-1.0, -3.0]


def test_system_charts() -> None:
    dispatch = pd.DataFrame(
        {
            "price": 50.0, "ccgt": 1000.0, "wind": 500.0, "coal": 0.0, "curtailment": 10.0,
            "emissions_t": 100.0,
        },
        index=HOURS,
    )  # fmt: skip
    stack = figures.generation_by_month(dispatch)
    assert [t.name for t in stack.data] == ["wind", "ccgt"]
    assert stack.data[1].y[0] == pytest.approx(1000.0 * 96 / 1e6)
    both = figures.system_by_month(dispatch)
    assert both.data[1].y[0] == pytest.approx(100.0 * 96 / 1e6)


def test_price_shape_charts() -> None:
    series = {"model": pd.Series(np.arange(96.0), index=HOURS)}
    duration = figures.price_duration(series)
    assert duration.data[0].y[0] == 95.0 and duration.data[0].x[-1] == 100.0
    hourly = figures.mean_by(series, "hour")
    assert len(hourly.data[0].x) == 24
    monthly = figures.mean_by(series, "month")
    assert list(monthly.data[0].x) == ["2019-01"]


def test_backcast_and_sweep_charts() -> None:
    years = pd.DataFrame({"year": [2019], "gas_twh_model": [120.0], "gas_twh_actual": [115.0]})
    fig = figures.model_vs_actual_by_year(years, {"Gas TWh": "gas_twh", "Coal": "coal_twh"})
    assert [t.name for t in fig.data] == ["Gas TWh model", "Gas TWh actual"]
    table = pd.DataFrame(
        {"a": [1, 2, 1], "b": ["x", "x", "y"], "total": [3.0, 2.0, 1.0],
         "revenue_per_mw_year": [30.0, 20.0, 10.0]}
    )  # fmt: skip
    ranking = figures.sweep_ranking(table, ["a", "b"])
    assert list(ranking.data[0].y) == ["1, x", "2, x", "1, y"]
    effect = figures.sweep_effect(table, "a")
    assert list(effect.data[0].y) == [20.0, 20.0]
