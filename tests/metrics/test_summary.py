import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from openenergy.assets import BatterySpec, BatteryState
from openenergy.backtest import BacktestResult
from openenergy.metrics import summarise


def result(revenue: list[float], forecast_error: float = 0.0, skipped: int = 0) -> BacktestResult:
    days = [date(2019, 1, d + 1) for d in range(len(revenue))]
    index = pd.date_range("2019-01-01", periods=len(revenue) * 2, freq="12h", tz="UTC")
    price = np.full(index.size, 50.0)
    intervals = pd.DataFrame(
        {
            "price": price,
            "forecast": price + forecast_error,
            "charge_mw": np.tile([1.0, 0.0], len(revenue)),
            "discharge_mw": np.tile([0.0, 0.9], len(revenue)),
            "energy_mwh": 1.0,
            "revenue": 0.0,
        },
        index=index,
    )
    daily = pd.DataFrame(
        {
            "revenue": revenue,
            "expected_revenue": revenue,
            "charged_mwh": 12.0,
            "discharged_mwh": 10.8,
            "equivalent_cycles": np.arange(1, len(revenue) + 1, dtype=float),
            "soh": 0.99,
            "energy_mwh": 1.0,
        },
        index=pd.Index(days),
    )
    return BacktestResult(
        spec=BatterySpec(power_mw=2.0, energy_mwh=4.0),
        intervals=intervals,
        daily=daily,
        skipped={date(2018, 12, d + 1): "no history" for d in range(skipped)},
        final_state=BatteryState(energy_mwh=1.0, soh=0.99, equivalent_cycles=len(revenue)),
        forecaster="naive_last_week",
        currency="GBP",
        step_hours=12.0,
    )


def test_summary_core_metrics() -> None:
    summary = summarise(result([100.0, 200.0, 300.0], skipped=2))
    assert summary.days == 3
    assert summary.skipped_days == 2
    assert summary.revenue == pytest.approx(600.0)
    assert summary.revenue_per_mw_year == pytest.approx(600.0 / 2.0 * 365 / 3)
    assert summary.charged_mwh == pytest.approx(36.0)
    assert summary.discharged_mwh == pytest.approx(32.4)
    assert summary.captured_spread == pytest.approx(600.0 / 32.4)
    assert summary.equivalent_cycles == pytest.approx(3.0)
    assert summary.final_soh == pytest.approx(0.99)
    assert summary.capture_ratio is None


def test_forecast_error_metrics() -> None:
    summary = summarise(result([1.0, 1.0], forecast_error=3.0))
    assert summary.forecast_mae == pytest.approx(3.0)
    assert summary.forecast_rmse == pytest.approx(3.0)


def test_capture_ratio_against_benchmark() -> None:
    summary = summarise(result([60.0, 20.0]), benchmark=result([100.0, 60.0]))
    assert summary.capture_ratio == pytest.approx(0.5)
    assert summary.benchmark_revenue == pytest.approx(160.0)


def test_capture_ratio_uses_common_days_only() -> None:
    main = result([60.0, 20.0])
    bench = result([100.0, 60.0, 500.0])
    assert summarise(main, benchmark=bench).capture_ratio == pytest.approx(0.5)


def test_capture_ratio_undefined_for_non_positive_benchmark() -> None:
    assert summarise(result([1.0]), benchmark=result([0.0])).capture_ratio is None


def test_no_discharge_gives_no_spread() -> None:
    main = result([0.0])
    main.daily["discharged_mwh"] = 0.0
    assert summarise(main).captured_spread is None


def test_summary_is_json_serialisable() -> None:
    payload = summarise(result([1.0, 2.0]), benchmark=result([2.0, 2.0])).to_dict()
    assert json.loads(json.dumps(payload))["capture_ratio"] == pytest.approx(0.75)
    assert payload["currency"] == "GBP"
