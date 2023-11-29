import numpy as np
import os
import pytest
import sys

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts import Battery  # noqa: E402


# Test for initialization
def test_initialization():
    battery = Battery(capacity_mwh=1.0, initial_soc=0.5)
    assert battery.capacity_mwh == 1.0
    assert battery.soc == 0.5
    assert battery.soh == 1.0


# Test for charging within capacity
def test_charge_within_capacity():
    battery = Battery(capacity_mwh=1.0, initial_soc=0.5)
    battery.charge(mwh=0.4, duration_hours=0.5)
    assert np.isclose(battery.soc, 0.86)


# Test for overcharging
def test_charge_over_capacity():
    battery = Battery(capacity_mwh=1.0, initial_soc=0.8)
    battery.charge(mwh=0.4, duration_hours=0.5)
    assert battery.soc == 1.0


# Test for discharging within capacity
def test_discharge_within_capacity():
    battery = Battery(capacity_mwh=1.0, initial_soc=0.5)
    battery.discharge(mwh=0.2, duration_hours=0.5)
    assert np.isclose(battery.soc, 0.32)


# Test for over-discharging
def test_discharge_below_zero():
    battery = Battery(capacity_mwh=1.0, initial_soc=0.1)
    battery.discharge(mwh=0.2, duration_hours=0.5)
    assert battery.soc == 0.0


# Test for SOH degradation
def test_soh_degradation():
    battery = Battery(capacity_mwh=1.0, initial_soc=0.5)
    initial_soh = battery.soh
    battery.charge(mwh=0.5, duration_hours=0.5)
    battery.discharge(mwh=0.5, duration_hours=0.5)
    assert battery.soh < initial_soh


# Test for charging efficiency
def test_charge_efficiency():
    battery = Battery(capacity_mwh=1.0, initial_soc=0.0, charge_efficiency=0.8)
    battery.charge(mwh=0.5, duration_hours=0.5)
    assert battery.soc == 0.4  # 0.5 MWh charged with 80% efficiency


# Test for discharging efficiency
def test_discharge_efficiency():
    battery = Battery(capacity_mwh=1.0, initial_soc=1.0, discharge_efficiency=0.8)
    battery.discharge(mwh=0.5, duration_hours=0.5)
    assert battery.soc == 0.6  # 0.5 MWh discharged with 80% efficiency


# Test for charge rate limit
def test_charge_rate_limit():
    battery = Battery(capacity_mwh=1.0, initial_soc=0.0, max_charge_rate=0.2)
    battery.charge(
        mwh=0.5, duration_hours=0.5
    )  # Attempt to charge at a rate higher than max_charge_rate
    assert np.isclose(
        battery.soc, 0.09
    )  # Only 0.2 MWh should be charged in half an hour


# Test for discharge rate limit
def test_discharge_rate_limit():
    battery = Battery(capacity_mwh=1.0, initial_soc=1.0, max_discharge_rate=0.2)
    battery.discharge(
        mwh=0.5, duration_hours=0.5
    )  # Attempt to discharge at a rate higher than max_discharge_rate
    assert np.isclose(
        battery.soc, 0.91
    )  # Only 0.2 MWh should be discharged in half an hour


# Test for invalid initialization values
def test_invalid_initialization():
    with pytest.raises(ValueError):
        Battery(capacity_mwh=-1.0, initial_soc=0.5)

    with pytest.raises(ValueError):
        Battery(capacity_mwh=1.0, initial_soc=-0.1)

    with pytest.raises(ValueError):
        Battery(capacity_mwh=1.0, initial_soc=1.1)


def test_long_term_degradation():
    battery = Battery(capacity_mwh=1.0, initial_soc=0.5)
    for _ in range(1000):  # Simulate many cycles
        battery.charge(mwh=0.5, duration_hours=0.5)
        battery.discharge(mwh=0.5, duration_hours=0.5)
    assert battery.soh < 1.0  # Expecting noticeable degradation


def test_full_charge_discharge_cycle():
    battery = Battery(capacity_mwh=1.0, initial_soc=0)
    battery.charge(mwh=1.0, duration_hours=1)
    assert np.isclose(battery.soc, 0.9)
    battery.discharge(mwh=1.0, duration_hours=1)
    assert np.isclose(battery.soc, 0.0)


def test_partial_charge_discharge():
    battery = Battery(capacity_mwh=1.0, initial_soc=0.25)
    battery.charge(mwh=0.25, duration_hours=0.5)
    assert np.isclose(battery.soc, 0.475)
    battery.discharge(mwh=0.15, duration_hours=0.5)
    assert np.isclose(battery.soc, 0.34)


def test_edge_case_soc_values():
    battery = Battery(capacity_mwh=1.0, initial_soc=0)
    battery.discharge(mwh=0.1, duration_hours=0.5)
    assert battery.soc == 0.0  # Cannot go below 0

    battery = Battery(capacity_mwh=1.0, initial_soc=1.0)
    battery.charge(mwh=0.1, duration_hours=0.5)
    assert battery.soc == 1.0  # Cannot exceed 1


if __name__ == "__main__":
    pytest.main()
