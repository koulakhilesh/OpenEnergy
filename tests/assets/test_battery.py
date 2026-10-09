import dataclasses

import numpy as np
import pytest

from openenergy import ConfigError, DispatchError
from openenergy.assets import BatterySpec, BatteryState, age, apply_dispatch


def spec(**overrides: float) -> BatterySpec:
    params: dict[str, float] = {
        "power_mw": 1.0,
        "energy_mwh": 2.0,
        "eta_charge": 0.9,
        "eta_discharge": 0.9,
        "initial_soc": 0.5,
    }
    params.update(overrides)
    return BatterySpec(**params)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("power_mw", 0.0),
        ("energy_mwh", -1.0),
        ("eta_charge", 0.0),
        ("eta_discharge", 1.01),
        ("soc_min", -0.1),
        ("soc_max", 1.1),
        ("initial_soc", 0.95),
        ("cycle_fade", -0.001),
        ("calendar_fade", 1.0),
        ("power_mw", float("nan")),
    ],
)
def test_spec_rejects_invalid_values(field: str, value: float) -> None:
    with pytest.raises(ConfigError, match=field):
        spec(**{"soc_min": 0.1, "soc_max": 0.9, field: value})


def test_spec_rejects_inverted_soc_window() -> None:
    with pytest.raises(ConfigError, match="soc_min"):
        spec(soc_min=0.6, soc_max=0.4, initial_soc=0.5)


def test_initial_state() -> None:
    state = spec(initial_soc=0.25).initial_state()
    assert state == BatteryState(energy_mwh=0.5)
    assert state.soh == 1.0
    assert state.equivalent_cycles == 0.0


def test_usable_energy_and_bounds_follow_soh() -> None:
    battery = spec(soc_min=0.1, soc_max=0.9)
    state = dataclasses.replace(battery.initial_state(), soh=0.5)
    assert battery.usable_energy_mwh(state) == pytest.approx(1.0)
    assert battery.energy_bounds(state) == pytest.approx((0.1, 0.9))


def test_charge_applies_charge_efficiency() -> None:
    battery = spec(initial_soc=0.0)
    result = apply_dispatch(battery, battery.initial_state(), [1.0], [0.0], step_hours=1.0)
    assert result.state.energy_mwh == pytest.approx(0.9)
    assert result.energy_mwh.tolist() == pytest.approx([0.0, 0.9])


def test_discharge_applies_discharge_efficiency() -> None:
    battery = spec(initial_soc=1.0)
    result = apply_dispatch(battery, battery.initial_state(), [0.0], [0.9], step_hours=1.0)
    assert result.state.energy_mwh == pytest.approx(1.0)


def test_round_trip_loses_both_efficiencies() -> None:
    battery = spec(initial_soc=0.0)
    charged = apply_dispatch(battery, battery.initial_state(), [1.0], [0.0], step_hours=1.0)
    delivered = charged.state.energy_mwh * battery.eta_discharge
    assert delivered == pytest.approx(1.0 * 0.9 * 0.9)


def test_half_hour_step_halves_energy() -> None:
    battery = spec(initial_soc=0.0)
    result = apply_dispatch(battery, battery.initial_state(), [1.0], [0.0], step_hours=0.5)
    assert result.state.energy_mwh == pytest.approx(0.45)


def test_trajectory_has_t_plus_one_points() -> None:
    battery = spec()
    result = apply_dispatch(battery, battery.initial_state(), [0.0] * 4, [0.0] * 4, 1.0)
    assert len(result.energy_mwh) == 5


def test_full_cycle_counts_once() -> None:
    battery = spec(eta_charge=1.0, eta_discharge=1.0, initial_soc=0.0)
    result = apply_dispatch(
        battery, battery.initial_state(), [1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 1.0], 1.0
    )
    assert result.state.throughput_mwh == pytest.approx(4.0)
    assert result.state.equivalent_cycles == pytest.approx(1.0)
    assert result.state.energy_mwh == pytest.approx(0.0)


def test_idle_intervals_do_not_add_cycles() -> None:
    battery = spec()
    result = apply_dispatch(battery, battery.initial_state(), [0.0] * 24, [0.0] * 24, 1.0)
    assert result.state.equivalent_cycles == 0.0
    assert result.state == battery.initial_state()


def test_cycles_accumulate_linearly_across_calls() -> None:
    battery = spec()
    state = battery.initial_state()
    for _ in range(3):
        state = apply_dispatch(battery, state, [0.1], [0.0], 1.0).state
        state = apply_dispatch(battery, state, [0.0], [0.1], 1.0).state
    assert state.throughput_mwh == pytest.approx(0.6)
    assert state.equivalent_cycles == pytest.approx(0.6 / (2 * 2.0))


def test_input_state_is_not_mutated() -> None:
    battery = spec()
    state = battery.initial_state()
    apply_dispatch(battery, state, [1.0], [0.0], 1.0)
    assert state == battery.initial_state()


@pytest.mark.parametrize(
    ("charge", "discharge", "message"),
    [
        ([1.5], [0.0], "power"),
        ([0.0], [1.5], "power"),
        ([-0.1], [0.0], "negative"),
        ([0.5], [0.5], "simultaneous"),
        ([1.0, 1.0], [0.0], "same length"),
        ([[1.0]], [[0.0]], "one-dimensional"),
        ([np.nan], [0.0], "finite"),
    ],
)
def test_rejects_invalid_dispatch(
    charge: list[float], discharge: list[float], message: str
) -> None:
    battery = spec()
    with pytest.raises(DispatchError, match=message):
        apply_dispatch(battery, battery.initial_state(), charge, discharge, 1.0)


def test_rejects_energy_above_max_with_interval() -> None:
    battery = spec(initial_soc=0.9, soc_max=0.9)
    with pytest.raises(DispatchError, match="interval 1"):
        apply_dispatch(battery, battery.initial_state(), [0.0, 1.0], [0.0, 0.0], 1.0)


def test_rejects_energy_below_min() -> None:
    battery = spec(initial_soc=0.1, soc_min=0.1)
    with pytest.raises(DispatchError, match="below"):
        apply_dispatch(battery, battery.initial_state(), [0.0], [0.5], 1.0)


def test_rejects_non_positive_step() -> None:
    battery = spec()
    with pytest.raises(DispatchError, match="step_hours"):
        apply_dispatch(battery, battery.initial_state(), [0.0], [0.0], 0.0)


def test_solver_noise_within_tolerance_is_clipped() -> None:
    battery = spec(initial_soc=0.0, eta_charge=1.0)
    result = apply_dispatch(battery, battery.initial_state(), [1.0 + 1e-9], [0.0], 2.0)
    assert result.state.energy_mwh == 2.0


def test_age_applies_cycle_and_calendar_fade() -> None:
    battery = spec(cycle_fade=1e-4, calendar_fade=0.02)
    state = dataclasses.replace(battery.initial_state(), equivalent_cycles=100.0)
    aged = age(battery, state, hours=365 * 24)
    assert aged.age_years == pytest.approx(1.0)
    assert aged.soh == pytest.approx(1.0 - 100 * 1e-4 - 0.02)


def test_age_is_not_compounding() -> None:
    battery = spec(calendar_fade=0.1)
    state = battery.initial_state()
    for _ in range(4):
        state = age(battery, state, hours=365 * 24 / 4)
    assert state.soh == pytest.approx(0.9)


def test_age_clips_stored_energy_to_shrunken_capacity() -> None:
    battery = spec(initial_soc=0.9, soc_max=0.9, calendar_fade=0.5)
    aged = age(battery, battery.initial_state(), hours=365 * 24)
    assert aged.soh == pytest.approx(0.5)
    assert aged.energy_mwh == pytest.approx(0.9 * 2.0 * 0.5)


def test_age_floors_soh_at_zero() -> None:
    battery = spec(calendar_fade=0.5)
    aged = age(battery, battery.initial_state(), hours=365 * 24 * 5)
    assert aged.soh == 0.0
    assert aged.energy_mwh == 0.0


def test_age_rejects_negative_hours() -> None:
    battery = spec()
    with pytest.raises(DispatchError, match="hours"):
        age(battery, battery.initial_state(), hours=-1.0)
