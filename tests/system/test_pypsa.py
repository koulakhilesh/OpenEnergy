import sys

import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError
from openenergy.system import Generator, Storage, SystemSpec, merit_order, solve

pytest.importorskip("pypsa")


def system(periods: int, freq: str, seed: int = 0, storage: tuple[Storage, ...] = ()) -> SystemSpec:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2019-03-01", periods=periods, freq=freq, tz="UTC")
    demand = pd.Series(rng.uniform(200, 900, periods), index=index)
    gens = [
        Generator(
            "nuclear",
            "nuclear",
            pd.Series(150.0, index=index),
            pd.Series(0.0, index=index),
            must_run=True,
        ),
        Generator(
            "wind",
            "wind",
            pd.Series(rng.uniform(0, 300, periods), index=index),
            pd.Series(0.0, index=index),
        ),
    ]
    for k in range(4):
        cost = pd.Series(30 + 10 * k + rng.uniform(0, 5, periods), index=index)
        gens.append(
            Generator(
                f"gas_{k}", "ccgt", pd.Series(150.0, index=index), cost, emissions_t_per_mwh=0.4
            )
        )
    return SystemSpec(demand, tuple(gens), storage, voll=3000.0)


@pytest.mark.parametrize("freq", ["1h", "30min"])
def test_pypsa_matches_merit_order_without_storage(freq: str) -> None:
    spec = system(96, freq)
    exact = merit_order(spec)
    lp = solve(spec, backend="pypsa")
    assert lp.backend == "pypsa"
    np.testing.assert_allclose(lp.price, exact.price, atol=1e-6)
    np.testing.assert_allclose(lp.generation, exact.generation, atol=1e-5)
    np.testing.assert_allclose(lp.unserved, exact.unserved, atol=1e-5)
    np.testing.assert_allclose(lp.emissions_t, exact.emissions_t, atol=1e-5)
    assert lp.cost == pytest.approx(exact.cost, rel=1e-9)
    assert (exact.unserved > 0).any()


def test_storage_moves_energy_from_cheap_to_dear_hours() -> None:
    index = pd.date_range("2019-03-01", periods=4, freq="1h", tz="UTC")
    demand = pd.Series([100.0, 100.0, 200.0, 200.0], index=index)
    gens = (
        Generator("cheap", "ccgt", pd.Series(150.0, index=index), pd.Series(10.0, index=index)),
        Generator("dear", "peaking", pd.Series(100.0, index=index), pd.Series(100.0, index=index)),
    )
    battery = Storage("battery", power_mw=40.0, hours=2.0, efficiency=0.81)
    without = solve(SystemSpec(demand, gens))
    with_storage = solve(SystemSpec(demand, gens, (battery,)))
    net = with_storage.storage["battery"]
    assert net.iloc[:2].sum() < 0 < net.iloc[2:].sum()
    # Round trip 0.81: what comes out is 81% of what went in.
    assert net.clip(lower=0).sum() == pytest.approx(0.81 * -net.clip(upper=0).sum(), rel=1e-6)
    supplied = with_storage.generation.sum(axis=1) + net + with_storage.unserved
    np.testing.assert_allclose(supplied, demand, atol=1e-6)
    assert with_storage.cost < without.cost
    assert "storage" in with_storage.by_technology().columns


def test_storage_on_a_real_sized_system_cuts_cost() -> None:
    spec = system(168, "1h", seed=3)
    battery = Storage("battery", power_mw=100.0, hours=4.0, efficiency=0.85)
    base = solve(spec)
    stored = solve(SystemSpec(spec.demand, spec.generators, (battery,), spec.voll))
    assert stored.backend == "pypsa"
    assert stored.cost <= base.cost
    assert stored.price.std() <= base.price.std()


def test_missing_pypsa_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pypsa", None)
    with pytest.raises(ConfigError, match=r"openenergy\[system\]"):
        solve(system(4, "1h"), backend="pypsa")
