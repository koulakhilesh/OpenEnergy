import dataclasses

import numpy as np
import pytest

from openenergy import ConfigError, DispatchError, InfeasibleDispatchError
from openenergy.assets import BatterySpec, apply_dispatch
from openenergy.dispatch import DispatchConfig, optimise_dispatch


def battery(**overrides: float) -> BatterySpec:
    params: dict[str, float] = {
        "power_mw": 1.0,
        "energy_mwh": 1.0,
        "eta_charge": 1.0,
        "eta_discharge": 1.0,
        "initial_soc": 0.0,
    }
    params.update(overrides)
    return BatterySpec(**params)


def test_buys_low_sells_high() -> None:
    spec = battery()
    plan = optimise_dispatch(spec, spec.initial_state(), [10.0, 50.0], step_hours=1.0)
    assert plan.charge_mw.tolist() == pytest.approx([1.0, 0.0])
    assert plan.discharge_mw.tolist() == pytest.approx([0.0, 1.0])
    assert plan.energy_mwh.tolist() == pytest.approx([0.0, 1.0, 0.0])
    assert plan.expected_revenue == pytest.approx(40.0)


def test_efficiency_losses() -> None:
    spec = battery(eta_charge=0.9, eta_discharge=0.9)
    plan = optimise_dispatch(spec, spec.initial_state(), [10.0, 50.0], step_hours=1.0)
    assert plan.expected_revenue == pytest.approx(0.81 * 50 - 10)


@pytest.mark.parametrize("prices", [[30.0, 30.0], [10.0, 12.0]])
def test_idle_when_spread_does_not_cover_losses(prices: list[float]) -> None:
    spec = battery(eta_charge=0.9, eta_discharge=0.9)
    plan = optimise_dispatch(spec, spec.initial_state(), prices, step_hours=1.0)
    assert plan.charge_mw.sum() == 0.0
    assert plan.discharge_mw.sum() == 0.0
    assert plan.expected_revenue == 0.0


def test_power_rating_limits_rate_not_energy() -> None:
    spec = battery(energy_mwh=4.0)
    plan = optimise_dispatch(spec, spec.initial_state(), [10, 10, 50, 50], step_hours=1.0)
    assert plan.charge_mw.max() == pytest.approx(1.0)
    assert plan.expected_revenue == pytest.approx(80.0)


def test_half_hourly_step() -> None:
    spec = battery()
    plan = optimise_dispatch(spec, spec.initial_state(), [10, 10, 50, 50], step_hours=0.5)
    assert plan.expected_revenue == pytest.approx(40.0)


def test_degraded_capacity_limits_energy() -> None:
    spec = battery(power_mw=2.0, energy_mwh=2.0)
    state = dataclasses.replace(spec.initial_state(), soh=0.5)
    plan = optimise_dispatch(spec, state, [10.0, 50.0], step_hours=1.0)
    assert plan.energy_mwh.max() == pytest.approx(1.0)
    assert plan.expected_revenue == pytest.approx(40.0)


@pytest.mark.parametrize(("cost", "expected"), [(15.0, 10.0), (25.0, 0.0)])
def test_degradation_cost(cost: float, expected: float) -> None:
    spec = battery()
    config = DispatchConfig(degradation_cost=cost)
    plan = optimise_dispatch(spec, spec.initial_state(), [10.0, 50.0], 1.0, config)
    assert plan.objective == pytest.approx(expected)


def test_cycle_cap() -> None:
    spec = battery()
    config = DispatchConfig(max_cycles=1.0)
    plan = optimise_dispatch(spec, spec.initial_state(), [10, 50, 10, 50], 1.0, config)
    assert (plan.charge_mw + plan.discharge_mw).sum() == pytest.approx(2.0)
    assert plan.expected_revenue == pytest.approx(40.0)


def test_returns_to_initial_energy_by_default() -> None:
    spec = battery(initial_soc=1.0)
    plan = optimise_dispatch(spec, spec.initial_state(), [50.0, 10.0], 1.0)
    assert plan.energy_mwh[-1] >= 1.0 - 1e-9
    assert plan.expected_revenue == pytest.approx(40.0)


def test_end_soc_target() -> None:
    spec = battery(energy_mwh=2.0)
    config = DispatchConfig(end_soc=0.5)
    plan = optimise_dispatch(spec, spec.initial_state(), [10.0, 10.0], 1.0, config)
    assert plan.energy_mwh[-1] == pytest.approx(1.0)
    assert plan.expected_revenue == pytest.approx(-10.0)


def test_unreachable_end_target_is_infeasible() -> None:
    spec = battery(energy_mwh=4.0)
    with pytest.raises(InfeasibleDispatchError):
        optimise_dispatch(
            spec, spec.initial_state(), [10.0, 10.0], 1.0, DispatchConfig(end_soc=1.0)
        )


def test_end_target_above_soc_max_is_infeasible() -> None:
    spec = battery(soc_max=0.8)
    with pytest.raises(InfeasibleDispatchError, match="end"):
        optimise_dispatch(
            spec, spec.initial_state(), [10.0, 10.0], 1.0, DispatchConfig(end_soc=0.9)
        )


def test_never_charges_and_discharges_together_at_negative_prices() -> None:
    spec = battery(eta_charge=0.9, eta_discharge=0.9, initial_soc=1.0)
    plan = optimise_dispatch(spec, spec.initial_state(), [-50.0, -50.0], 1.0)
    assert not ((plan.charge_mw > 0) & (plan.discharge_mw > 0)).any()
    assert plan.expected_revenue == pytest.approx(50 * (1 - 0.81))


def test_plan_is_physically_feasible() -> None:
    rng = np.random.default_rng(7)
    spec = battery(
        energy_mwh=2.0, eta_charge=0.92, eta_discharge=0.94, soc_min=0.1, initial_soc=0.5
    )
    prices = rng.normal(50, 25, size=48)
    plan = optimise_dispatch(spec, spec.initial_state(), prices, 0.5)
    outcome = apply_dispatch(spec, spec.initial_state(), plan.charge_mw, plan.discharge_mw, 0.5)
    assert outcome.energy_mwh == pytest.approx(plan.energy_mwh, abs=1e-6)
    revenue = float(prices @ (plan.discharge_mw - plan.charge_mw) * 0.5)
    assert plan.expected_revenue == pytest.approx(revenue)
    assert plan.expected_revenue > 0


@pytest.mark.parametrize(
    ("prices", "message"),
    [([], "at least one"), ([1.0, np.nan], "finite"), ([[1.0, 2.0]], "one-dimensional")],
)
def test_rejects_bad_prices(prices: list[float], message: str) -> None:
    spec = battery()
    with pytest.raises(DispatchError, match=message):
        optimise_dispatch(spec, spec.initial_state(), prices, 1.0)


def test_rejects_non_positive_step() -> None:
    spec = battery()
    with pytest.raises(DispatchError, match="step_hours"):
        optimise_dispatch(spec, spec.initial_state(), [1.0], 0.0)


@pytest.mark.parametrize(
    ("field", "value"),
    [("degradation_cost", -1.0), ("max_cycles", 0.0), ("end_soc", 1.5), ("mip_rel_gap", -0.1)],
)
def test_config_validation(field: str, value: float) -> None:
    with pytest.raises(ConfigError, match=field):
        DispatchConfig(**{field: value})
