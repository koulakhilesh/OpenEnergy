import os
import pytest
import datetime
import sys

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts.prices import SimulatedPriceModel  # noqa: E402


@pytest.fixture
def simulated_price_model():
    return SimulatedPriceModel()


def test_get_prices(simulated_price_model):
    date = datetime.date(2022, 1, 1)
    original_prices, prices_with_noise_and_spikes = simulated_price_model.get_prices(
        date
    )

    assert isinstance(original_prices, list)
    assert isinstance(prices_with_noise_and_spikes, list)
    assert len(original_prices) == 24
    assert len(prices_with_noise_and_spikes) == 24


def test_price_envelope(simulated_price_model):
    date = datetime.date(2022, 1, 1)
    prices = simulated_price_model.price_envelope(date=date)

    assert isinstance(prices, list)
    assert len(prices) == 24
    assert all(isinstance(price, float) for price in prices)


def test_add_noise_and_spikes(simulated_price_model):
    prices = [10, 20, 30, 40, 50]
    noisy_prices = simulated_price_model.add_noise_and_spikes(prices)

    assert isinstance(noisy_prices, list)
    assert len(noisy_prices) == 5
    assert all(isinstance(price, float) for price in noisy_prices)
    assert all(price >= 0 for price in noisy_prices)
    assert any(
        price != original_price for price, original_price in zip(noisy_prices, prices)
    )


if __name__ == "__main__":
    pytest.main()
