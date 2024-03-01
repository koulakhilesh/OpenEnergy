import numpy as np
import os
import pytest
import sys

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts.prices import PriceModel  # noqa: E402


# Test for initialization
def test_initialization():
    price_model = PriceModel()
    price_model.get_average_price_for_date("2018-01-01")


if __name__ == "__main__":
    pytest.main()
