import os
import sys
from datetime import datetime

import pytest

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts.prices import HistoricalAveragePriceModel
from scripts.shared import CSVDataProvider


@pytest.mark.parametrize("create_test_csv", ["GB_GBN_price_day_ahead"], indirect=True)
def test_historical_average_price_model(create_test_csv):
    csv_path = os.path.join("tests", "test.csv")
    csv_data_provider = CSVDataProvider(csv_path)
    model = HistoricalAveragePriceModel(data_provider=csv_data_provider)
    date = datetime(2022, 1, 7)

    average_prices_last_week, prices_current_date = model.get_prices(date)

    assert average_prices_last_week is not None
    assert prices_current_date is not None


if __name__ == "__main__":
    pytest.main([__file__])
