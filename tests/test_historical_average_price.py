import os
import pytest
import pandas as pd
import sys
from datetime import datetime
from pandas.testing import assert_frame_equal

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts.prices import CSVDataProvider, HistoricalAveragePriceModel  # noqa: E402


def test_csv_data_provider(create_test_csv):
    csv_data_provider = CSVDataProvider("test.csv")
    data = csv_data_provider.get_data()

    expected_data = pd.DataFrame(
        {
            "utc_timestamp": pd.date_range(
                start="2021-12-31T00:00:00Z", periods=24 * 8, freq="H"
            ),
            "GB_GBN_price_day_ahead": range(24 * 8),
        }
    )
    assert_frame_equal(data, expected_data)


def test_historical_average_price_model(create_test_csv):
    data_provider = CSVDataProvider("test.csv")
    model = HistoricalAveragePriceModel(data_provider=data_provider)
    date = datetime(2022, 1, 7)

    average_prices_last_week, prices_current_date = model.get_prices(date)

    assert average_prices_last_week is not None
    assert prices_current_date is not None


if __name__ == "__main__":
    pytest.main()
