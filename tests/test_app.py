import os
import sys
from unittest.mock import patch

import pytest

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from app import main  # noqa: E402


def test_app_default_args():
    # Test with default arguments
    results = main()
    assert results is not None


def test_app_custom_battery_params():
    # Test with different battery parameters
    args = [
        "app.py",
        "--battery_capacity",
        "2.0",
        "--charge_efficiency",
        "0.8",
        "--discharge_efficiency",
        "0.8",
    ]
    with patch.object(sys, "argv", args):
        results = main()
    assert results is not None


def test_app_custom_dates():
    # Test with different start and end dates
    args = ["app.py", "--start_date", "2021-01-01", "--end_date", "2021-01-02"]
    with patch.object(sys, "argv", args):
        results = main()
    assert results is not None


if __name__ == "__main__":
    pytest.main()
