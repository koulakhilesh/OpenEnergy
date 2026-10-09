import dataclasses

import numpy as np
import pytest

from openenergy import ConfigError, DispatchError
from openenergy.assets import BatterySpec, apply_dispatch
from openenergy.dispatch import (
    DispatchConfig,
    GridConnection,
    dispatch_plant,
    optimise_colocated,
    optimise_dispatch,
)


def battery(**overrides: float) -> BatterySpec:
    params: dict[str, float] = {
        "power_mw": 1.0,
        "energy_mwh": 2.0,
        "eta_charge": 1.0,
        "eta_discharge": 1.0,
        "initial_soc": 0.0,
    }
    params.update(overrides)
    return BatterySpec(**params)


def test_battery_recaptures_clipped_output() -> None:
    spec = battery()
    plan = optimise_colocated(
        spec, spec.initial_state(), [2, 2, 0, 0], [10, 10, 50, 50], 1.0, GridConnection(1.0)
    )
    assert plan.plant_to_grid_mw.tolist() == pytest.approx([1, 1, 0, 0])
    assert plan.plant_to_battery_mw.tolist() == pytest.approx([1, 1, 0, 0])
    assert plan.curtailed_mw.sum() == pytest.approx(0.0)
    assert plan.discharge_mw.tolist() == pytest.approx([0, 0, 1, 1])
    assert plan.expected_revenue == pytest.approx(120.0)


def test_plant_alone_clips_and_sells() -> None:
    plan = dispatch_plant([2, 2, 0, 0], [10, 10, 50, 50], 1.0, GridConnection(1.0))
    assert plan.plant_to_grid_mw.tolist() == pytest.approx([1, 1, 0, 0])
    assert plan.curtailed_mw.tolist() == pytest.approx([1, 1, 0, 0])
    assert plan.expected_revenue == pytest.approx(20.0)


@pytest.mark.parametrize(("premium", "exported"), [(0.0, 0.0), (30.0, 1.0)])
def test_curtails_below_minus_premium(premium: float, exported: float) -> None:
    spec = battery(energy_mwh=1.0, initial_soc=1.0)
    grid = GridConnection(5.0, premium_per_mwh=premium)
    plan = optimise_colocated(spec, spec.initial_state(), [1.0], [-20.0], 1.0, grid)
    assert plan.plant_to_grid_mw[0] == pytest.approx(exported)
    assert plan.curtailed_mw[0] == pytest.approx(1.0 - exported)
    assert plan.expected_premium == pytest.approx(premium * exported)
    alone = dispatch_plant([1.0], [-20.0], 1.0, grid)
    assert alone.plant_to_grid_mw[0] == pytest.approx(exported)


def test_no_grid_charging_without_import() -> None:
    spec = battery()
    blocked = optimise_colocated(
        spec, spec.initial_state(), [0, 0], [10, 50], 1.0, GridConnection(1.0, import_limit_mw=0)
    )
    assert blocked.grid_to_battery_mw.sum() == 0.0
    assert blocked.expected_revenue == pytest.approx(0.0)
    allowed = optimise_colocated(
        spec, spec.initial_state(), [0, 0], [10, 50], 1.0, GridConnection(1.0)
    )
    assert allowed.expected_revenue == pytest.approx(40.0)


def test_export_limit_caps_plant_plus_discharge() -> None:
    spec = battery(initial_soc=1.0)
    config = DispatchConfig(end_soc=0.0)
    plan = optimise_colocated(
        spec, spec.initial_state(), [1, 1], [50, 50], 1.0, GridConnection(1.5), config
    )
    assert plan.export_mw.tolist() == pytest.approx([1.5, 1.5])
    assert plan.expected_revenue == pytest.approx(150.0)


def test_without_plant_matches_standalone_battery() -> None:
    rng = np.random.default_rng(3)
    spec = battery(eta_charge=0.92, eta_discharge=0.94, initial_soc=0.5)
    prices = rng.normal(50, 20, 24)
    colocated = optimise_colocated(
        spec, spec.initial_state(), np.zeros(24), prices, 1.0, GridConnection(1.0)
    )
    alone = optimise_dispatch(spec, spec.initial_state(), prices, 1.0)
    assert colocated.expected_revenue == pytest.approx(alone.expected_revenue)


def test_plan_balances_and_is_physically_feasible() -> None:
    rng = np.random.default_rng(11)
    spec = battery(power_mw=2.0, energy_mwh=4.0, eta_charge=0.95, eta_discharge=0.95)
    available = np.clip(rng.normal(2.0, 1.5, 48), 0, 4)
    prices = rng.normal(40, 30, 48)
    grid = GridConnection(2.5, import_limit_mw=1.0, premium_per_mwh=10.0)
    plan = optimise_colocated(spec, spec.initial_state(), available, prices, 0.5, grid)

    split = plan.plant_to_grid_mw + plan.plant_to_battery_mw + plan.curtailed_mw
    assert split == pytest.approx(available, abs=1e-6)
    assert plan.charge_mw == pytest.approx(plan.plant_to_battery_mw + plan.grid_to_battery_mw)
    assert plan.export_mw.max() <= 2.5 + 1e-6
    assert plan.grid_to_battery_mw.max() <= 1.0 + 1e-6
    assert not ((plan.plant_to_grid_mw > 0) & (plan.grid_to_battery_mw > 0)).any()
    assert not ((plan.charge_mw > 0) & (plan.discharge_mw > 0)).any()
    outcome = apply_dispatch(spec, spec.initial_state(), plan.charge_mw, plan.discharge_mw, 0.5)
    assert outcome.energy_mwh == pytest.approx(plan.energy_mwh, abs=1e-6)
    assert plan.expected_revenue == pytest.approx(float(prices @ plan.export_mw * 0.5))


def test_colocation_never_worse_than_separate_assets() -> None:
    rng = np.random.default_rng(5)
    spec = battery(eta_charge=0.95, eta_discharge=0.95, initial_soc=0.5)
    available = np.clip(rng.normal(1.0, 0.8, 24), 0, 2)
    prices = rng.normal(45, 25, 24)
    plant_grid = GridConnection(2.0)
    together = optimise_colocated(
        spec, spec.initial_state(), available, prices, 1.0, GridConnection(3.0)
    )
    plant = dispatch_plant(available, prices, 1.0, plant_grid)
    alone = optimise_dispatch(spec, spec.initial_state(), prices, 1.0)
    assert together.objective >= plant.objective + alone.objective - 1e-6


def test_degraded_battery_and_state_respected() -> None:
    spec = battery()
    state = dataclasses.replace(spec.initial_state(), soh=0.5)
    plan = optimise_colocated(spec, state, [2, 2, 0, 0], [10, 10, 50, 50], 1.0, GridConnection(1.0))
    assert plan.energy_mwh.max() <= 1.0 + 1e-9


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"export_limit_mw": -1.0}, "export_limit_mw"),
        ({"export_limit_mw": 1.0, "import_limit_mw": -1.0}, "import_limit_mw"),
        ({"export_limit_mw": 1.0, "premium_per_mwh": float("nan")}, "premium_per_mwh"),
    ],
)
def test_grid_validation(kwargs: dict[str, float], message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        GridConnection(**kwargs)


def test_import_defaults_to_export_limit() -> None:
    assert GridConnection(3.0).import_limit_mw == 3.0


@pytest.mark.parametrize(
    ("available", "message"),
    [([1.0], "same length"), ([1.0, -1.0], "non-negative"), ([1.0, np.nan], "finite")],
)
def test_rejects_bad_available(available: list[float], message: str) -> None:
    spec = battery()
    with pytest.raises(DispatchError, match=message):
        optimise_colocated(
            spec, spec.initial_state(), available, [1.0, 2.0], 1.0, GridConnection(1)
        )
    with pytest.raises(DispatchError, match=message):
        dispatch_plant(available, [1.0, 2.0], 1.0, GridConnection(1))
