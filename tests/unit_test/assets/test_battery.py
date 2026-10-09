import os
import sys

import pytest

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from scripts.assets.battery import (
    BasicSOHCalculator,
    Battery,
    TemperatureEfficiencyAdjuster,
)


def test_temperature_efficiency_adjuster():
    adjuster = TemperatureEfficiencyAdjuster()
    charge_efficiency, discharge_efficiency = adjuster.adjust_efficiency(30, 0.9, 0.9)
    assert charge_efficiency == 0.85
    assert discharge_efficiency == 0.85


def test_basic_soh_calculator():
    calculator = BasicSOHCalculator()
    soh = calculator.calculate_soh(1.0, 1.0, 0.5)
    assert abs(soh - 0.999995) < 1e-6


def test_battery_initialization():
    battery = Battery(1.0)
    assert battery.capacity_mwh == 1.0
    assert battery.charge_efficiency == 0.9
    assert battery.discharge_efficiency == 0.9
    assert isinstance(battery.efficiency_adjuster, TemperatureEfficiencyAdjuster)
    assert isinstance(battery.soh_calculator, BasicSOHCalculator)


def test_battery_charge():
    battery = Battery(1.0)
    battery.charge(0.5)
    assert battery.soc == 0.95
    assert battery.energy_cycled_mwh == 0.5


def test_battery_discharge():
    battery = Battery(1.0)
    battery.soc = 1.0
    battery.discharge(0.5)
    assert battery.soc == 0.55
    assert battery.energy_cycled_mwh == 0.5


def test_battery_update_soh_and_cycles():
    battery = Battery(1.0)
    battery.soc = 1.0
    battery.update_soh_and_cycles(0.5)
    assert battery.soh < 1.0
    assert battery.energy_cycled_mwh == 0.5


def test_battery_check_and_update_cycles():
    battery = Battery(1.0)
    battery.energy_cycled_mwh = 1.0
    battery.check_and_update_cycles()
    assert battery.cycle_count == 0.5
    assert battery.energy_cycled_mwh == 1.0


def test_battery_adjust_efficiency_for_temperature():
    battery = Battery(1.0, temperature_c=35)
    battery.adjust_efficiency_for_temperature()
    assert battery.charge_efficiency < 0.9
    assert battery.discharge_efficiency < 0.9


def test_battery_invalid_initial_conditions():
    with pytest.raises(ValueError):
        Battery(-1.0)
    with pytest.raises(ValueError):
        Battery(1.0, initial_soc=1.5)
    with pytest.raises(ValueError):
        Battery(1.0, initial_soh=1.5)


def test_battery_charge_above_capacity():
    battery = Battery(1.0)
    battery.charge(2.0)
    assert battery.soc == 1.0
    assert battery.energy_cycled_mwh == 1.0


def test_battery_discharge_below_zero():
    battery = Battery(1.0)
    battery.discharge(2.0)
    assert battery.soc == 0.0
    assert battery.energy_cycled_mwh == 1.0


def test_battery_charge_and_discharge():
    battery = Battery(1.0)
    battery.charge(0.5)
    battery.discharge(0.5)
    assert battery.soc == 0.49999999999999994
    assert battery.energy_cycled_mwh == 1.0


def test_battery_charge_with_max_charge_rate():
    battery = Battery(1.0, max_charge_rate_mw=0.5)
    battery.charge(1.0)
    assert battery.soc == 0.95
    assert battery.energy_cycled_mwh == 0.5


def test_battery_discharge_with_max_discharge_rate():
    battery = Battery(1.0, max_discharge_rate_mw=0.5)
    battery.soc = 1.0
    battery.discharge(1.0)
    assert battery.soc == 0.55
    assert battery.energy_cycled_mwh == 0.5


def test_battery_update_soh_and_cycles_with_high_dod():
    battery = Battery(1.0)
    battery.soc = 1.0
    battery.update_soh_and_cycles(1.0)
    assert battery.soh < 1.0
    assert battery.energy_cycled_mwh == 1.0


def test_battery_check_and_update_cycles_with_high_energy_cycled():
    battery = Battery(1.0)
    battery.energy_cycled_mwh = 2.0
    battery.check_and_update_cycles()
    assert battery.cycle_count == 1.0
    assert battery.energy_cycled_mwh == 2.0


if __name__ == "__main__":
    pytest.main([__file__])
