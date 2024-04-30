import os
import pytest
import pandas as pd
import numpy as np
import datetime
import sys

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts.prices import HistoricalAveragePriceModel  # noqa: E402


# Sample Data Provider
class SampleDataProvider:
    def get_data(self):
        # Sample price data
        data = pd.DataFrame(
            {
                "utc_timestamp": pd.date_range(
                    start="2021-12-31T00:00:00Z", periods=24 * 8, freq="H"
                ),
                "GB_GBN_price_day_ahead": [10.0] * 24 * 4 + [20.0] * 24 * 4,
            }
        )
        return data


def test_get_prices():
    # Create a sample instance of HistoricalAveragePriceModel
    data_provider = SampleDataProvider()
    model = HistoricalAveragePriceModel(data_provider)

    # Specify a date for testing
    date = datetime.date(2022, 1, 7)

    # Expected results
    average_prices_last_week = [14.28571] * 24
    prices_current_date = [20.0] * 24

    # Call the method under test
    result_average_prices, result_prices = model.get_prices(date)

    # Check the results
    assert np.isclose(
        np.array(result_average_prices), np.array(average_prices_last_week)
    ).all()
    assert np.isclose(np.array(result_prices), np.array(prices_current_date)).all()


if __name__ == "__main__":
    pytest.main()
