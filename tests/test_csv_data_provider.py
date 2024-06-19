import os
import sys

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts.shared import CSVDataProvider


@pytest.mark.parametrize("create_test_csv", ["GB_GBN_price_day_ahead"], indirect=True)
def test_csv_data_provider(create_test_csv):
    csv_path = os.path.join("tests", "test.csv")
    csv_data_provider = CSVDataProvider(csv_path)
    data = csv_data_provider.get_data(
        column_names=["GB_GBN_price_day_ahead"], timestamp_column="utc_timestamp"
    )

    expected_data = pd.DataFrame(
        {
            "utc_timestamp": pd.date_range(
                start="2021-12-31T00:00:00Z", periods=24 * 8, freq="h"
            ),
            "GB_GBN_price_day_ahead": [float(i) for i in range(24 * 8)],
        }
    )
    expected_data = expected_data.set_index("utc_timestamp")
    expected_data.index.name = None
    expected_data = expected_data[["GB_GBN_price_day_ahead"]]

    assert_frame_equal(data, expected_data)


if __name__ == "__main__":
    pytest.main([__file__])
