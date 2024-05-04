import os

import pandas as pd
import pytest


@pytest.fixture(scope="session", autouse=True)
def create_test_csv():
    data = {
        "utc_timestamp": pd.date_range(
            start="2021-12-31T00:00:00Z", periods=24 * 8, freq="H"
        ),
        "GB_GBN_price_day_ahead": range(24 * 8),
    }

    df = pd.DataFrame(data)
    df.to_csv("test.csv", index=False)

    yield

    os.remove("test.csv")
