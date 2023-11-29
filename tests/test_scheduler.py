import os
import pytest
import pandas as pd
import sys

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts import Battery, MarketScheduler  # noqa: E402


def test_market_scheduler():
    test_battery = Battery(capacity_mwh=1.0, initial_soc=0.5)
    # Lower prices for the first half, higher for the second
    test_prices = [20] * 24 + [40] * 24

    scheduler = MarketScheduler(test_battery, test_prices)
    schedule_df = scheduler.create_schedule()

    # Check the DataFrame structure
    assert isinstance(schedule_df, pd.DataFrame)
    assert "Interval" in schedule_df.columns
    assert "Action" in schedule_df.columns
    assert "Value" in schedule_df.columns

    # Basic validation of the schedule
    # First half should be primarily charging
    for i in range(24):
        assert schedule_df.at[i, "Action"] in ["charge", "idle"]

    # Second half should be primarily discharging
    for i in range(24, 48):
        assert schedule_df.at[i, "Action"] in ["discharge", "idle"]


if __name__ == "__main__":
    pytest.main()
