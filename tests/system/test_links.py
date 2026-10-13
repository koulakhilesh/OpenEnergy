import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError, DataError
from openenergy.system import Generator, Link, SystemSpec, solve
from openenergy.system.commitment import Commitment, UnitParameters

pytest.importorskip("pypsa")

INDEX = pd.date_range("2024-03-01", periods=4, freq="1h", tz="UTC")


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


def test_imports_when_the_neighbour_is_cheaper() -> None:
    result = solve(spec(link(50.0, hurdle=5.0)))
    assert result.backend == "pypsa"
    assert result.links is not None
    np.testing.assert_allclose(result.links["ifa"], 200.0, atol=1e-6)
    np.testing.assert_allclose(result.price, 80.0, atol=1e-6)
    assert (result.by_technology()["interconnectors"] == result.links["ifa"]).all()


def test_exports_cheap_surplus_and_sets_the_price() -> None:
    # Free wind exceeds demand; the neighbour pays 60 less a 5 hurdle for 200 MW of it.
    result = solve(spec(link(60.0, hurdle=5.0), demand=300.0, wind=900.0))
    assert result.links is not None
    np.testing.assert_allclose(result.links["ifa"], -200.0, atol=1e-6)
    np.testing.assert_allclose(result.curtailment, 400.0, atol=1e-6)
    np.testing.assert_allclose(result.price, 0.0, atol=1e-6)


def test_link_sets_the_price_when_not_at_its_limit() -> None:
    result = solve(spec(link(50.0, hurdle=5.0, mw=1000.0)))
    np.testing.assert_allclose(result.price, 55.0, atol=1e-6)


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


def test_merit_and_commitment_reject_links() -> None:
    system = spec(link(50.0))
    with pytest.raises(ConfigError, match="links"):
        solve(system, backend="merit")
    with pytest.raises(ConfigError, match="links"):
        solve(system, commitment=Commitment({"ccgt": UnitParameters(100.0, 0.5, 0.0)}))
