from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError
from openenergy.data import SystemInputs
from openenergy.system import Generator, Storage, SystemSpec, merit_order, solve
from openenergy.system.commitment import Commitment, UnitParameters, commit

ROOT = Path(__file__).parents[2]


def index(periods: int) -> pd.DatetimeIndex:
    return pd.date_range("2019-03-01", periods=periods, freq="1h", tz="UTC")


def gen(
    idx: pd.DatetimeIndex, name: str, mw: float, cost: float, tech: str | None = None
) -> Generator:
    return Generator(name, tech or name, pd.Series(mw, index=idx), pd.Series(cost, index=idx))


def two_days(night: float = 100.0, day: float = 200.0) -> pd.Series:
    idx = index(48)
    hours = idx.hour
    return pd.Series(np.where((hours < 6) | (hours >= 22), night, day), index=idx, dtype=float)


def test_without_start_costs_it_matches_the_merit_order() -> None:
    rng = np.random.default_rng(1)
    idx = index(72)
    demand = pd.Series(rng.uniform(150, 650, len(idx)), index=idx)
    gens = (
        gen(idx, "base", 200.0, 5.0),
        Generator(
            "gas_1",
            "ccgt",
            pd.Series(300.0, index=idx),
            pd.Series(rng.uniform(30, 35, len(idx)), index=idx),
        ),
        Generator(
            "gas_2",
            "ccgt",
            pd.Series(300.0, index=idx),
            pd.Series(rng.uniform(40, 45, len(idx)), index=idx),
        ),
    )
    spec = SystemSpec(demand, gens, voll=3000.0)
    free = Commitment({"ccgt": UnitParameters(50.0, 0.0, 0.0)})
    uc = commit(spec, free)
    exact = merit_order(spec)
    np.testing.assert_allclose(uc.price, exact.price, atol=1e-6)
    np.testing.assert_allclose(uc.generation, exact.generation, atol=1e-6)
    assert uc.cost == pytest.approx(exact.cost, rel=1e-9)
    assert uc.backend == "commitment"


def test_start_costs_keep_a_unit_on_overnight() -> None:
    demand = two_days(night=100.0, day=230.0)
    idx = demand.index
    gens = (gen(idx, "base", 150.0, 10.0), gen(idx, "mid", 100.0, 50.0, "ccgt"))
    spec = SystemSpec(demand, gens)
    costly = commit(spec, Commitment({"ccgt": UnitParameters(100.0, 0.5, 200.0)}))
    assert costly.units_online is not None and costly.starts is not None
    # The final night has no lookahead beyond it, so only the first 40 hours are checked.
    first = slice(0, 40)
    assert (costly.units_online["mid"].iloc[first] >= 1).all()
    assert costly.generation["mid"].iloc[first].min() >= 50.0 - 1e-6
    assert costly.starts["mid"].iloc[1:40].sum() == pytest.approx(0.0)
    cheap = commit(spec, Commitment({"ccgt": UnitParameters(100.0, 0.5, 0.0)}))
    assert cheap.units_online is not None
    assert (cheap.units_online["mid"] == 0).any()
    night = (idx.hour >= 1) & (idx.hour < 6)
    assert (costly.price[night] == 10.0).all()
    assert (costly.price[~night & (idx.hour >= 8) & (idx.hour < 21)] == 50.0).all()


def test_it_starts_a_unit_rather_than_shed_a_sliver_of_load() -> None:
    idx = index(24)
    demand = pd.Series(100.0, index=idx)
    demand.iloc[12] = 100.01
    gens = (gen(idx, "base", 100.0, 10.0), gen(idx, "mid", 200.0, 50.0, "ccgt"))
    spec = SystemSpec(demand, gens, voll=6000.0)
    result = commit(spec, Commitment({"ccgt": UnitParameters(100.0, 0.5, 1000.0)}))
    assert result.unserved.sum() == 0.0
    assert result.price.max() < 6000.0
    assert result.units_online is not None and result.units_online["mid"].iloc[12] == 1
    short = commit(
        SystemSpec(demand + 200.0, gens, voll=6000.0),
        Commitment({"ccgt": UnitParameters(100.0, 0.5, 1000.0)}),
    )
    assert short.unserved.iloc[12] == pytest.approx(0.01)
    assert short.price.iloc[12] == pytest.approx(6000.0)


def test_start_price_adds_start_costs_over_each_run() -> None:
    demand = two_days(night=100.0, day=200.0)
    idx = demand.index
    gens = (gen(idx, "base", 150.0, 10.0), gen(idx, "mid", 100.0, 50.0, "ccgt"))
    spec = SystemSpec(demand, gens)
    result = commit(spec, Commitment({"ccgt": UnitParameters(100.0, 0.5, 2.0)}))
    assert result.start_price is not None and result.starts is not None
    assert (result.start_price >= result.price - 1e-9).all()
    started = result.starts["mid"] > 0.5
    assert started.iloc[1:].any()
    runs_above = result.start_price > result.price + 1e-6
    assert runs_above.any()


def test_balance_and_unit_limits_hold() -> None:
    rng = np.random.default_rng(4)
    idx = index(96)
    demand = pd.Series(rng.uniform(300, 900, len(idx)), index=idx)
    gens = (
        Generator(
            "nuclear",
            "nuclear",
            pd.Series(150.0, index=idx),
            pd.Series(0.0, index=idx),
            must_run=True,
        ),
        Generator(
            "wind",
            "wind",
            pd.Series(rng.uniform(0, 300, len(idx)), index=idx),
            pd.Series(0.0, index=idx),
        ),
        gen(idx, "ccgt_1", 450.0, 40.0, "ccgt"),
        gen(idx, "coal_1", 400.0, 45.0, "coal"),
        gen(idx, "peak", 100.0, 120.0, "peaking"),
    )
    units = {
        "ccgt": UnitParameters(150.0, 0.4, 30.0),
        "coal": UnitParameters(200.0, 0.2, 40.0),
        "peaking": UnitParameters(25.0, 0.25, 15.0),
    }
    battery = Storage("battery", 50.0, 2.0, 0.81)
    spec = SystemSpec(demand, gens, (battery,), voll=3000.0)
    result = solve(spec, commitment=Commitment(units, lookahead_hours=12))
    supplied = result.generation.sum(axis=1) + result.storage["battery"] + result.unserved
    np.testing.assert_allclose(supplied, demand, atol=1e-5)
    assert result.units_online is not None
    online = result.units_online
    np.testing.assert_allclose(online, online.round(), atol=1e-6)
    for name, tech in (("ccgt_1", "ccgt"), ("coal_1", "coal"), ("peak", "peaking")):
        unit = units[tech]
        output = result.generation[name]
        assert (output <= online[name] * unit.unit_mw + 1e-6).all()
        assert (output >= online[name] * unit.unit_mw * unit.min_stable - 1e-6).all()
    assert result.storage["battery"].abs().max() <= 50.0 + 1e-6


def test_parameter_validation() -> None:
    for args, match in (
        ((0.0, 0.5, 1.0), "unit_mw"),
        ((10.0, 1.0, 1.0), "min_stable"),
        ((10.0, 0.5, -1.0), "start_cost"),
    ):
        with pytest.raises(ConfigError, match=match):
            UnitParameters(*args)
    with pytest.raises(ConfigError, match="at least one"):
        Commitment({})
    with pytest.raises(ConfigError, match="lookahead"):
        Commitment({"ccgt": UnitParameters(1.0, 0.0, 0.0)}, lookahead_hours=-1)
    idx = index(4)
    spec = SystemSpec(pd.Series(1.0, index=idx), (gen(idx, "a", 2.0, 1.0),))
    with pytest.raises(ConfigError, match="own solver"):
        solve(spec, backend="merit", commitment=Commitment({"a": UnitParameters(1.0, 0.0, 0.0)}))


def test_bundled_unit_parameters() -> None:
    commitment = Commitment.from_inputs(SystemInputs(ROOT / "data/system"))
    assert set(commitment.units) == {"ccgt", "coal", "peaking"}
    ccgt = commitment.units["ccgt"]
    assert ccgt.unit_mw == 500.0
    assert ccgt.min_stable == 0.4
    assert ccgt.start_cost_per_mw == pytest.approx(55 * 0.6235, abs=0.01)
