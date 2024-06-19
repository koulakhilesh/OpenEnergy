import os
import sys
from unittest.mock import patch

import pytest

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from main import run_simulation  # noqa: E402


def test_app_default_args():
    # Test with default arguments
    results = run_simulation()
    assert results is not None


def test_app_custom_battery_params():
    # Test with different battery parameters
    args = [
        "main.py",
        "--battery_capacity",
        "2.0",
        "--charge_efficiency",
        "0.8",
        "--discharge_efficiency",
        "0.8",
    ]
    with patch.object(sys, "argv", args):
        results = run_simulation()
    assert results is not None


def test_app_custom_dates():
    # Test with different start and end dates
    args = ["main.py", "--start_date", "2021-01-01", "--end_date", "2021-01-02"]
    with patch.object(sys, "argv", args):
        results = run_simulation()
    assert results is not None


# TODO Add test for ForecastedPriceModel
def test_app_price_model_selection(create_test_csv):
    # Test with different price models
    for price_model in ["SimulatedPriceModel", "HistoricalPriceModel"]:
        args = ["main.py", "--price_model", price_model]
        with patch.object(sys, "argv", args):
            results = run_simulation()
        assert results is not None


def test_main_exception_handling():
    # Mock the create_dependencies function to raise an exception
    with patch("main.create_dependencies", side_effect=Exception("Test exception")):
        # Call the main function
        result = run_simulation()

        # Check if the main function returned None
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__])
