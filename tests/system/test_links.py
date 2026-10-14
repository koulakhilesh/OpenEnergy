import importlib.util

import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError, DataError
from openenergy.system import Generator, Link, Storage, SystemSpec, solve
from openenergy.system.commitment import Commitment, UnitParameters

INDEX = pd.date_range("2024-03-01", periods=4, freq="1h", tz="UTC")
HAS_PYPSA = importlib.util.find_spec("pypsa") is not None
BACKENDS = [
    pytest.param("pypsa", marks=pytest.mark.skipif(not HAS_PYPSA, reason="needs pypsa")),
    "merit",
]
FREE = Commitment({"ccgt": UnitParameters(50.0, 0.0, 0.0)})


def flat(value: float) -> pd.Series:
    return pd.Series(value, index=INDEX)


def spec(link: Link, demand: float = 500.0, wind: float = 0.0) -> SystemSpec:
    return SystemSpec(
        flat(demand),
        (
            Generator("wind", "wind", flat(wind), flat(0.0)),
            Generator("gas", "ccgt", flat(1000.0), flat(80.0), emissions_t_per_mwh=0.4),
        ),
        links=(link,),
    )


def link(price: float, hurdle: float = 0.0, mw: float = 200.0) -> Link:
    return Link("ifa", flat(mw), flat(mw), flat(price), hurdle)


@pytest.mark.parametrize("backend", BACKENDS)
def test_imports_when_the_neighbour_is_cheaper(backend: str) -> None:
    result = solve(spec(link(50.0, hurdle=5.0)), backend)  # type: ignore[arg-type]
    assert result.backend == backend
    assert result.links is not None
    np.testing.assert_allclose(result.links["ifa"], 200.0, atol=1e-6)
    np.testing.assert_allclose(result.price, 80.0, atol=1e-6)
    assert (result.by_technology()["interconnectors"] == result.links["ifa"]).all()
    assert list(result.generation.columns) == ["wind", "gas"]
    # Gas 300 MW at 80 and imports 200 MW at 55, for four hours.
    assert result.cost == pytest.approx(4 * (300 * 80 + 200 * 55), rel=1e-6)


@pytest.mark.parametrize("backend", BACKENDS)
def test_exports_cheap_surplus_and_sets_the_price(backend: str) -> None:
    # Free wind exceeds demand; the neighbour pays 60 less a 5 hurdle for 200 MW of it.
    system = spec(link(60.0, hurdle=5.0), demand=300.0, wind=900.0)
    result = solve(system, backend)  # type: ignore[arg-type]
    assert result.links is not None
    np.testing.assert_allclose(result.links["ifa"], -200.0, atol=1e-6)
    np.testing.assert_allclose(result.curtailment, 400.0, atol=1e-6)
    np.testing.assert_allclose(result.price, 0.0, atol=1e-6)
    assert result.cost == pytest.approx(-4 * 200 * 55, rel=1e-6)


@pytest.mark.parametrize("backend", BACKENDS)
def test_link_sets_the_price_when_not_at_its_limit(backend: str) -> None:
    result = solve(spec(link(50.0, hurdle=5.0, mw=1000.0)), backend)  # type: ignore[arg-type]
    np.testing.assert_allclose(result.price, 55.0, atol=1e-6)


def test_auto_uses_the_merit_order_for_links_without_storage() -> None:
    assert solve(spec(link(50.0))).backend == "merit"


def test_must_run_may_exceed_demand_by_the_export_capacity() -> None:
    nuclear = Generator("nuclear", "nuclear", flat(600.0), flat(0.0), must_run=True)
    system = SystemSpec(flat(500.0), (nuclear,), links=(link(40.0),))
    result = solve(system)
    assert result.links is not None
    np.testing.assert_allclose(result.links["ifa"], -100.0, atol=1e-6)
    with pytest.raises(DataError):
        solve(SystemSpec(flat(500.0), (nuclear,), links=(link(40.0, mw=50.0),)))


def test_links_are_validated() -> None:
    other = pd.date_range("2025-01-01", periods=4, freq="1h", tz="UTC")
    with pytest.raises(DataError, match="share the demand index"):
        spec(Link("x", pd.Series(1.0, index=other), flat(1.0), flat(1.0)))
    with pytest.raises(DataError, match="non-negative"):
        spec(Link("x", flat(-1.0), flat(1.0), flat(1.0)))
    with pytest.raises(DataError, match="missing"):
        spec(Link("x", flat(1.0), flat(1.0), flat(np.nan)))
    with pytest.raises(ConfigError, match="hurdle"):
        spec(Link("x", flat(1.0), flat(1.0), flat(1.0), hurdle=-1.0))


def random_system(seed: int = 3, periods: int = 72, storage: bool = False) -> SystemSpec:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-03-01", periods=periods, freq="1h", tz="UTC")

    def series(values: np.ndarray) -> pd.Series:
        return pd.Series(values, index=index)

    zero = series(np.zeros(periods))
    gens = (
        Generator("nuclear", "nuclear", series(np.full(periods, 150.0)), zero, must_run=True),
        Generator("wind", "wind", series(rng.uniform(0, 500, periods)), zero),
        Generator(
            "gas_1", "ccgt", series(np.full(periods, 300.0)), series(rng.uniform(40, 45, periods))
        ),
        Generator(
            "gas_2", "ccgt", series(np.full(periods, 300.0)), series(rng.uniform(55, 60, periods))
        ),
    )
    links = tuple(
        Link(
            name,
            series(np.full(periods, mw)),
            series(np.full(periods, mw)),
            series(rng.uniform(20, 80, periods)),
            hurdle,
        )
        for name, mw, hurdle in (("ifa", 200.0, 2.0), ("nsl", 150.0, 0.0))
    )
    stores = (Storage("battery", 100.0, 2.0, 0.9),) if storage else ()
    return SystemSpec(series(rng.uniform(300, 900, periods)), gens, stores, 3000.0, links)


@pytest.mark.skipif(not HAS_PYPSA, reason="needs pypsa")
def test_merit_and_pypsa_agree_on_links() -> None:
    system = random_system()
    merit, pypsa = solve(system, "merit"), solve(system, "pypsa")
    np.testing.assert_allclose(merit.price, pypsa.price, atol=1e-6)
    assert merit.cost == pytest.approx(pypsa.cost, rel=1e-6)
    assert merit.links is not None and pypsa.links is not None
    np.testing.assert_allclose(merit.links.sum(axis=1), pypsa.links.sum(axis=1), atol=1e-4)


def test_commitment_with_links_matches_the_merit_order_without_start_costs() -> None:
    system = random_system()
    uc, exact = solve(system, commitment=FREE), solve(system, "merit")
    assert uc.backend == "commitment"
    np.testing.assert_allclose(uc.price, exact.price, atol=1e-6)
    assert uc.cost == pytest.approx(exact.cost, rel=1e-6)
    assert uc.links is not None and exact.links is not None
    np.testing.assert_allclose(uc.links.sum(axis=1), exact.links.sum(axis=1), atol=1e-4)
    assert list(uc.generation.columns) == [g.name for g in system.generators]


def test_commitment_with_links_and_storage() -> None:
    system = random_system(storage=True)
    costly = Commitment({"ccgt": UnitParameters(100.0, 0.5, 500.0)})
    result = solve(system, commitment=costly)
    assert result.links is not None
    for each in system.links:
        flows = result.links[each.name]
        assert (flows <= each.import_mw + 1e-6).all()
        assert (flows >= -each.export_mw - 1e-6).all()
    assert result.start_price is not None
    assert (result.start_price >= result.price - 1e-6).all()


def test_merit_still_rejects_storage() -> None:
    with pytest.raises(ConfigError, match="storage"):
        solve(random_system(storage=True), "merit")
