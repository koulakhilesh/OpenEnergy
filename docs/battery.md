# Battery Module Documentation

This module contains classes and methods for simulating a battery's behavior, including its efficiency, state of health (SOH), and charging and discharging processes.

## Classes

### EfficiencyAdjuster

This is an abstract base class (ABC) that defines the interface for adjusting the efficiency of a battery based on certain parameters.

```python
class EfficiencyAdjuster(ABC):
    @abstractmethod
    def adjust_efficiency(self, temperature_c, charge_efficiency, discharge_efficiency):
        pass
```

### TemperatureEfficiencyAdjuster

This class inherits from `EfficiencyAdjuster` and implements the `adjust_efficiency` method. It adjusts the charge and discharge efficiencies based on the temperature.

```python
class TemperatureEfficiencyAdjuster(EfficiencyAdjuster):
    def adjust_efficiency(self, temperature_c, charge_efficiency, discharge_efficiency):
        temp_effect = abs(temperature_c - 25) * 0.01
        new_charge_efficiency = max(0.5, min(charge_efficiency - temp_effect, 1.0))
        new_discharge_efficiency = max(
            0.5, min(discharge_efficiency - temp_effect, 1.0)
        )
        return new_charge_efficiency, new_discharge_efficiency
```

The temperature effect is calculated as:

```latex
\text{{temp\_effect}} = | \text{{temperature\_c}} - 25 | * 0.01
```

The new charge and discharge efficiencies are calculated as:

```latex
\text{{new\_charge\_efficiency}} = \max(0.5, \min(\text{{charge\_efficiency}} - \text{{temp\_effect}}, 1.0))
\text{{new\_discharge\_efficiency}} = \max(0.5, \min(\text{{discharge\_efficiency}} - \text{{temp\_effect}}, 1.0))
```

### SOHCalculator

This is an abstract base class that defines the interface for calculating the state of health (SOH) of a battery.

```python
class SOHCalculator(ABC):
    @abstractmethod
    def calculate_soh(self, soh, energy_cycled_mwh, dod):
        pass
```

### BasicSOHCalculator

This class inherits from `SOHCalculator` and implements the `calculate_soh` method. It calculates the SOH based on the current SOH, the energy cycled, and the depth of discharge (DOD).

```python
class BasicSOHCalculator(SOHCalculator):
    def calculate_soh(self, soh, energy_cycled_mwh, dod):
        base_degradation = 0.000005
        dod_factor = 2 if dod > 0.5 else 1
        degradation_rate = base_degradation * energy_cycled_mwh * dod_factor
        return soh * (1 - degradation_rate)
```

The degradation rate is calculated as:

```latex
\text{{degradation\_rate}} = \text{{base\_degradation}} * \text{{energy\_cycled\_mwh}} * \text{{dod\_factor}}
```

The new SOH is calculated as:

```latex
\text{{new\_soh}} = \text{{soh}} * (1 - \text{{degradation\_rate}})
```

### Battery

This class represents a battery. It has methods for validating initial conditions, adjusting efficiency for temperature, charging, discharging, and updating the SOH and cycles.

```python
class Battery:
    def __init__(
        self,
        capacity_mwh,
        charge_efficiency=0.9,
        discharge_efficiency=0.9,
        efficiency_adjuster=None,
        soh_calculator=None,
        **kwargs,
    ):
        # Initialization code omitted for brevity
```

The `charge` and `discharge` methods adjust the battery's state of charge (SOC) based on the energy input/output and the charge/discharge efficiency. The SOC is calculated as:

```latex
\text{{new\_soc}} = \min(\text{{soc}} + \frac{{\text{{actual\_energy\_mwh}}}}{{\text{{capacity\_mwh}}}}, 1.0) \quad \text{{for charging}}
\text{{new\_soc}} = \max(\text{{soc}} - \frac{{\text{{actual\_energy\_mwh}}}}{{\text{{capacity\_mwh}}}}, 0.0) \quad \text{{for discharging}}
```

The `update_soh_and_cycles` method updates the energy cycled and the SOH, and checks and updates the cycles. The DOD is calculated as:

```latex
\text{{dod}} = 1.0 - \text{{soc}}
```

The cycles are calculated as:

```latex
\text{{cycles}} = \frac{{\text{{energy\_cycled\_mwh}}}}{{2 * \text{{capacity\_mwh}}}}
```

The `check_and_update_cycles` method updates the cycle count and the last cycle SOC.