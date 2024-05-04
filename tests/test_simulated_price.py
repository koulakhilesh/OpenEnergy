import os
import pytest
from datetime import datetime
import sys
from unittest.mock import Mock, patch

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts.prices import (  # noqa: E402
    SimulatedPriceEnvelopeGenerator,
    SimulatedPriceModel,
    SimulatedPriceNoiseAdder,
)


def test_simulated_price_envelope_generator():
    generator = SimulatedPriceEnvelopeGenerator()
    date = datetime(2022, 1, 1)
    prices = generator.generate(date)
    assert len(prices) == 24


def test_simulated_price_noise_adder():
    adder = SimulatedPriceNoiseAdder()
    prices = [10, 20, 30, 40, 50]
    prices_with_noise = adder.add(prices)
    assert len(prices_with_noise) == len(prices)


def test_simulated_price_model():
    mock_envelope_generator = Mock(spec=SimulatedPriceEnvelopeGenerator)
    mock_envelope_generator.generate.return_value = [10, 20, 30, 40, 50]

    mock_noise_adder = Mock(spec=SimulatedPriceNoiseAdder)
    mock_noise_adder.add.return_value = [11, 21, 31, 41, 51]

    model = SimulatedPriceModel(
        envelope_generator=mock_envelope_generator, noise_adder=mock_noise_adder
    )
    date = datetime(2022, 1, 1)
    prices, prices_with_noise_and_spikes = model.get_prices(date)

    mock_envelope_generator.generate.assert_called_once_with(date=date)
    mock_noise_adder.add.assert_called_once_with([10, 20, 30, 40, 50])
    assert prices == [10, 20, 30, 40, 50]
    assert prices_with_noise_and_spikes == [11, 21, 31, 41, 51]


def test_add_increases_price_when_random_less_than_spike_chance():
    # Arrange
    noise_adder = SimulatedPriceNoiseAdder(
        noise_level=0, spike_chance=1.0, spike_multiplier=1.5
    )
    prices = [10.0]

    with patch("random.random", return_value=0.01), patch(
        "random.uniform", return_value=0.0
    ):
        # Act
        noisy_prices = noise_adder.add(prices)

        # Assert
        assert noisy_prices[0] == 15.0  # 10.0 * 1.5


if __name__ == "__main__":
    pytest.main()
