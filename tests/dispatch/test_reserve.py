import numpy as np
import pytest

from openenergy import ConfigError, DispatchError
from openenergy.assets import BatterySpec, apply_dispatch
from openenergy.data.response import SERVICES
from openenergy.dispatch import DispatchConfig, Reserve, optimise_dispatch


def spec(**overrides: float) -> BatterySpec:
    params: dict[str, float] = {"power_mw": 1.0, "energy_mwh": 2.0, "initial_soc": 0.5}
    params.update(overrides)
    return BatterySpec(**params)


def reserve(
    names: list[str],
    block: list[int],
    price: list[list[float]],
    utilisation: list[list[float]] | None = None,
    **kwargs: object,
) -> Reserve:
    prices = np.array(price, dtype=float)
    used = np.zeros_like(prices) if utilisation is None else np.array(utilisation, dtype=float)
    return Reserve(
        tuple(SERVICES[n] for n in names),
        np.array(block),
        prices,
        used,
        **kwargs,  # type: ignore[arg-type]
    )


def test_flat_prices_hold_full_power_both_ways() -> None:
    battery = spec()
    options = reserve(["DCL", "DCH"], [0, 0, 1, 1], [[5.0, 2.0], [5.0, 2.0]])
    plan = optimise_dispatch(battery, battery.initial_state(), [50.0] * 4, 1.0, reserve=options)
    assert plan.reserve_mw is not None
    assert plan.reserve_mw.ravel().tolist() == pytest.approx([1.0] * 4)
    assert plan.expected_response == pytest.approx(4 * 7.0)
    assert plan.objective == pytest.approx(28.0)


def test_reserve_shares_power_headroom_with_trading() -> None:
    battery = spec(eta_charge=1.0, eta_discharge=1.0)
    options = reserve(["DCL"], [0, 0], [[3.0]])
    plan = optimise_dispatch(battery, battery.initial_state(), [0.0, 100.0], 1.0, reserve=options)
    assert plan.reserve_mw is not None
    held = plan.reserve_mw[0, 0]
    assert (plan.discharge_mw - plan.charge_mw + held).max() <= 1.0 + 1e-9
    # Trading the 100 spread beats holding DC low at 3 per hour.
    assert plan.discharge_mw[1] == pytest.approx(1.0)
    assert held == pytest.approx(0.0)


def test_energy_held_for_the_service_duration() -> None:
    battery = spec(initial_soc=0.25, eta_charge=0.95, eta_discharge=0.95)
    options = reserve(["DRL", "DRH"], [0], [[10.0, 10.0]])
    plan = optimise_dispatch(battery, battery.initial_state(), [50.0], 1.0, reserve=options)
    assert plan.reserve_mw is not None
    # 0.5 MWh stored covers one hour of DR low at 0.475 MW; DR high has room for full power.
    assert plan.reserve_mw[0].tolist() == pytest.approx([0.475, 1.0])


def test_utilisation_moves_energy_and_matches_battery_physics() -> None:
    battery = spec()
    options = reserve(["DRH"], [0, 0, 0, 0], [[4.0]], [[0.1]])
    state = battery.initial_state()
    plan = optimise_dispatch(battery, state, [40.0] * 4, 1.0, reserve=options)
    assert plan.response_charge_mw is not None and plan.response_discharge_mw is not None
    assert plan.response_charge_mw.tolist() == pytest.approx([0.1] * 4)
    outcome = apply_dispatch(
        battery,
        state,
        plan.charge_mw,
        plan.discharge_mw,
        1.0,
        plan.response_charge_mw,
        plan.response_discharge_mw,
    )
    assert outcome.energy_mwh.tolist() == pytest.approx(plan.energy_mwh.tolist())
    # The energy DR high delivered for free is sold to return to the starting energy.
    assert plan.discharge_mw.sum() > 0
    assert plan.expected_revenue > 0


def test_paid_utilisation_energy_is_settled_at_the_interval_price() -> None:
    battery = spec()
    free = reserve(["DRH"], [0, 0], [[4.0]], [[0.1]])
    paid = reserve(["DRH"], [0, 0], [[4.0]], [[0.1]], energy_paid=True)
    plans = [
        optimise_dispatch(battery, battery.initial_state(), [40.0, 40.0], 1.0, reserve=options)
        for options in (free, paid)
    ]
    assert plans[0].reserve_mw is not None and plans[1].reserve_mw is not None
    held = plans[1].reserve_mw[0, 0]
    assert plans[1].expected_revenue == pytest.approx(
        plans[0].expected_revenue - 2 * 0.1 * held * 40.0, abs=1e-6
    )


def test_fixed_reservations_are_honoured() -> None:
    battery = spec()
    fixed = np.array([[0.3], [np.nan]])
    options = reserve(["DCL"], [0, 1], [[5.0], [5.0]], fixed=fixed)
    plan = optimise_dispatch(battery, battery.initial_state(), [50.0, 50.0], 1.0, reserve=options)
    assert plan.reserve_mw is not None
    assert plan.reserve_mw[:, 0].tolist() == pytest.approx([0.3, 1.0])


def test_intervals_outside_blocks_cannot_reserve() -> None:
    battery = spec()
    options = reserve(["DCL"], [-1, 0], [[5.0]])
    plan = optimise_dispatch(battery, battery.initial_state(), [50.0, 50.0], 1.0, reserve=options)
    assert plan.expected_response == pytest.approx(5.0)


def test_cycle_cap_counts_utilisation() -> None:
    battery = spec()
    options = reserve(["DRL", "DRH"], [0] * 4, [[10.0, 10.0]], [[0.25, 0.25]])
    config = DispatchConfig(max_cycles=0.1)
    plan = optimise_dispatch(
        battery, battery.initial_state(), [50.0] * 4, 1.0, config, reserve=options
    )
    assert plan.reserve_mw is not None
    # Throughput 0.5 MWh per MW reserved per hour x 4 hours <= 2 * 0.1 * 2 MWh.
    assert plan.reserve_mw.sum() * 0.25 * 4 <= 0.4 + 1e-6


def test_degradation_cost_applies_to_utilisation() -> None:
    battery = spec()
    options = reserve(["DRL", "DRH"], [0], [[1.0, 1.0]], [[0.2, 0.2]])
    config = DispatchConfig(degradation_cost=10.0)
    plan = optimise_dispatch(battery, battery.initial_state(), [0.0], 1.0, config, reserve=options)
    assert plan.reserve_mw is not None
    # Wear of 0.2 MWh x GBP 10 per MW exceeds the GBP 1 fee, and free energy is worth nothing.
    assert plan.reserve_mw.sum() == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"utilisation": [[2.0]]}, "utilisation must be in"),
        ({"price": [[1.0], [2.0]]}, "price must have shape"),
        ({"price": [[np.nan]]}, "must be finite"),
        ({"beyond_hours": np.array([1.0, 2.0])}, "beyond_hours"),
    ],
)
def test_reserve_validation(kwargs: dict[str, object], message: str) -> None:
    args: dict[str, object] = {"names": ["DCL"], "block": [0], "price": [[1.0]]}
    args.update(kwargs)
    with pytest.raises(ConfigError, match=message):
        reserve(**args)  # type: ignore[arg-type]


def test_block_map_must_match_horizon() -> None:
    battery = spec()
    options = reserve(["DCL"], [0], [[1.0]])
    with pytest.raises(ConfigError, match="block map"):
        optimise_dispatch(battery, battery.initial_state(), [1.0, 2.0], 1.0, reserve=options)


def test_apply_dispatch_response_flows() -> None:
    battery = spec(eta_charge=1.0, eta_discharge=1.0)
    state = battery.initial_state()
    outcome = apply_dispatch(battery, state, [0.0], [0.0], 1.0, [0.2], [0.1])
    assert outcome.energy_mwh.tolist() == pytest.approx([1.0, 1.1])
    assert outcome.state.throughput_mwh == pytest.approx(0.3)
    with pytest.raises(DispatchError, match="must match"):
        apply_dispatch(battery, state, [0.0], [0.0], 1.0, [0.1, 0.1], None)
