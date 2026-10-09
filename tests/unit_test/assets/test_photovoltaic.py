import os
import sys

import pytest

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)
from scripts.assets.photovoltaic import PVSystem


@pytest.fixture
def pv_system():
    return PVSystem(capacity_mw=10)


@pytest.mark.parametrize(
    "years, expected_efficiency",
    [(0, 1.0), (1, 0.99), (2, 0.9801), (5, 0.95099005), (10, 0.90438208)],
)
def test_calculate_current_efficiency(pv_system, years, expected_efficiency):
    assert pv_system.calculate_current_efficiency(years) == pytest.approx(
        expected_efficiency, abs=1e-6
    )


@pytest.mark.parametrize(
    "normalized_irradiance, years, expected_generation",
    [
        (1.0, 0, 10.0),
        (0.5, 1, 4.95),
        (0.8, 2, 7.8408),
        (0.3, 5, 2.852970),
    ],
)
def test_calculate_generation(
    pv_system,
    normalized_irradiance,
    years,
    expected_generation,
):
    assert pv_system.calculate_generation(
        normalized_irradiance, years
    ) == pytest.approx(expected_generation, abs=1e-6)


if __name__ == "__main__":
    pytest.main([__file__])
