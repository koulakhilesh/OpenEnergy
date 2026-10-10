from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError, DataError
from openenergy.data import EMISSION_FACTORS, GenerationMixSource, SystemInputs
from openenergy.system import (
    Adjustments,
    FleetAssumptions,
    Generator,
    Storage,
    SystemSpec,
    build_system,
    merit_order,
    solve,
    thermal_generators,
)

ROOT = Path(__file__).parents[2]
BUNDLED = ROOT / "data/system"
INDEX = pd.date_range("2019-06-01", periods=4, freq="1h", tz="UTC")


def series(values: list[float] | float) -> pd.Series:
    if isinstance(values, float | int):
        values = [float(values)] * len(INDEX)
    return pd.Series(values, index=INDEX, dtype=float)


def gen(name: str, mw: list[float] | float, cost: list[float] | float, **kw: object) -> Generator:
    return Generator(name, kw.pop("technology", name), series(mw), series(cost), **kw)  # type: ignore[arg-type]


def test_merit_order_stacks_cheapest_first() -> None:
    spec = SystemSpec(
        series([50.0, 120.0, 180.0, 10.0]),
        (gen("cheap", 100.0, 10.0), gen("mid", 60.0, 30.0), gen("dear", 50.0, 90.0)),
    )
    result = merit_order(spec)
    assert result.price.tolist() == [10.0, 30.0, 90.0, 10.0]
    assert result.generation["cheap"].tolist() == [50.0, 100.0, 100.0, 10.0]
    assert result.generation["mid"].tolist() == [0.0, 20.0, 60.0, 0.0]
    assert result.generation["dear"].tolist() == [0.0, 0.0, 20.0, 0.0]
    assert result.unserved.sum() == 0
    assert result.cost == pytest.approx(10 * 260 + 30 * 80 + 90 * 20)
    balance = result.generation.sum(axis=1) + result.unserved
    assert np.allclose(balance, spec.demand)


def test_shortfall_is_shed_at_voll() -> None:
    spec = SystemSpec(series(150.0), (gen("only", 100.0, 20.0),), voll=5000.0)
    result = solve(spec)
    assert result.unserved.tolist() == [50.0] * 4
    assert result.price.tolist() == [5000.0] * 4
    assert result.cost == pytest.approx(4 * (100 * 20 + 50 * 5000))


def test_must_run_and_curtailment() -> None:
    spec = SystemSpec(
        series([100.0, 100.0, 100.0, 100.0]),
        (
            gen("nuclear", 60.0, 0.0, must_run=True),
            gen("wind", [10.0, 50.0, 80.0, 0.0], 0.0),
            gen("gas", 100.0, 40.0, emissions_t_per_mwh=0.4),
        ),
    )
    result = solve(spec)
    assert result.generation["nuclear"].tolist() == [60.0] * 4
    assert result.generation["wind"].tolist() == [10.0, 40.0, 40.0, 0.0]
    assert result.curtailment.tolist() == [0.0, 10.0, 40.0, 0.0]
    assert result.price.tolist() == [40.0, 0.0, 0.0, 40.0]
    assert result.emissions_t.tolist() == pytest.approx([12.0, 0.0, 0.0, 16.0])
    by_tech = result.by_technology()
    assert set(by_tech.columns) == {"nuclear", "wind", "gas", "unserved"}


def test_zero_capacity_units_do_not_set_price() -> None:
    spec = SystemSpec(series(50.0), (gen("solar", 0.0, 0.0), gen("gas", 100.0, 40.0)), voll=1000.0)
    assert merit_order(spec).price.tolist() == [40.0] * 4


def test_time_varying_costs_reorder_the_stack() -> None:
    spec = SystemSpec(
        series(50.0),
        (gen("gas", 50.0, [20.0, 60.0, 20.0, 60.0]), gen("coal", 50.0, 40.0)),
    )
    result = merit_order(spec)
    assert result.generation["gas"].tolist() == [50.0, 0.0, 50.0, 0.0]
    assert result.price.tolist() == [20.0, 40.0, 20.0, 40.0]


def test_must_run_above_demand_is_an_error() -> None:
    spec = SystemSpec(series(50.0), (gen("nuclear", 80.0, 0.0, must_run=True),))
    with pytest.raises(DataError, match="must-run output exceeds demand in 4"):
        solve(spec)


def test_spec_validation() -> None:
    with pytest.raises(ConfigError, match="at least one"):
        SystemSpec(series(1.0), ())
    with pytest.raises(ConfigError, match="duplicate"):
        SystemSpec(series(1.0), (gen("a", 1.0, 1.0), gen("a", 1.0, 1.0)))
    with pytest.raises(DataError, match="share the demand index"):
        SystemSpec(
            series(1.0),
            (Generator("a", "a", series(1.0).iloc[:2], series(1.0).iloc[:2]),),
        )
    with pytest.raises(DataError, match="missing"):
        SystemSpec(series([1.0, np.nan, 1.0, 1.0]), (gen("a", 1.0, 1.0),))
    with pytest.raises(DataError, match="non-negative"):
        SystemSpec(series(-1.0), (gen("a", 1.0, 1.0),))
    with pytest.raises(DataError, match="capacity_mw must be non-negative"):
        SystemSpec(series(1.0), (gen("a", -1.0, 1.0),))
    with pytest.raises(DataError, match="marginal_cost has missing"):
        SystemSpec(series(1.0), (gen("a", 1.0, [1.0, np.nan, 1.0, 1.0]),))
    with pytest.raises(ConfigError, match="voll"):
        SystemSpec(series(1.0), (gen("a", 1.0, 1.0),), voll=0.0)


def test_storage_validation_and_backend_choice() -> None:
    for kwargs, match in (
        ({"power_mw": 0.0, "hours": 1.0, "efficiency": 0.9}, "power_mw"),
        ({"power_mw": 1.0, "hours": -1.0, "efficiency": 0.9}, "hours"),
        ({"power_mw": 1.0, "hours": 1.0, "efficiency": 1.5}, "efficiency"),
    ):
        with pytest.raises(ConfigError, match=match):
            Storage("s", **kwargs)  # type: ignore[arg-type]
    spec = SystemSpec(series(1.0), (gen("a", 1.0, 1.0),), (Storage("s", 1.0, 1.0, 0.9),))
    with pytest.raises(ConfigError, match="cannot dispatch storage"):
        solve(spec, backend="merit")
    with pytest.raises(ConfigError, match="backend"):
        solve(SystemSpec(series(1.0), (gen("a", 1.0, 1.0),)), backend="other")  # type: ignore[arg-type]


def write_inputs(directory: Path) -> SystemInputs:
    pd.DataFrame(
        {
            "year": [2018, 2019],
            "ccgt_mw": [1000.0, 1000.0],
            "coal_mw": [500.0, 500.0],
            "gas_turbine_mw": [60.0, 60.0],
            "oil_engine_mw": [40.0, 40.0],
            "nuclear_mw": [100.0, 100.0],
            "pumped_storage_mw": [50.0, 50.0],
            "ccgt_efficiency": [0.5, 0.5],
            "coal_efficiency": [0.35, 0.35],
        }
    ).to_csv(directory / "fleet.csv", index=False)
    pd.DataFrame(
        {
            "year": [2019] * 4,
            "quarter": [1, 2, 3, 4],
            "coal_p_per_kwh": [1.0] * 4,
            "oil_p_per_kwh": [4.0] * 4,
            "gas_p_per_kwh": [2.0] * 4,
        }
    ).to_csv(directory / "fuel_prices.csv", index=False)
    pd.DataFrame(
        {
            "valid_from": ["2018-04-01"],
            "eu_ets_usd_per_t": [20.0],
            "fx_date": ["2018-03-29"],
            "usd_per_eur": [1.0],
            "gbp_per_eur": [1.0],
            "cps_gas_gbp_per_kwh": [0.002],
            "cps_coal_gbp_per_gj": [1.0],
        }
    ).to_csv(directory / "carbon_prices.csv", index=False)
    return SystemInputs(directory)


def test_thermal_tranches_cost_and_capacity(tmp_path: Path) -> None:
    inputs = write_inputs(tmp_path)
    assumptions = FleetAssumptions(tranches=3, availability=0.8, ccgt_spread=0.05)
    gens = {g.name: g for g in thermal_generators(INDEX, inputs, assumptions)}
    assert sorted(gens) == ["ccgt_1", "ccgt_2", "ccgt_3", "coal_1", "coal_2", "coal_3", "peaking_1"]
    gas_fuel = 20.0 + 2.0 + 20.0 * EMISSION_FACTORS["gas"]
    assert gens["ccgt_1"].marginal_cost.iloc[0] == pytest.approx(gas_fuel / 0.45)
    assert gens["ccgt_2"].marginal_cost.iloc[0] == pytest.approx(gas_fuel / 0.50)
    assert gens["ccgt_3"].marginal_cost.iloc[0] == pytest.approx(gas_fuel / 0.55)
    assert gens["ccgt_1"].capacity_mw.iloc[0] == pytest.approx(1000 * 0.8 / 3)
    assert gens["ccgt_2"].emissions_t_per_mwh == pytest.approx(EMISSION_FACTORS["gas"] / 0.5)
    coal_fuel = 10.0 + 3.6 + 20.0 * EMISSION_FACTORS["coal"]
    assert gens["coal_2"].marginal_cost.iloc[0] == pytest.approx(coal_fuel / 0.35)
    assert gens["peaking_1"].capacity_mw.iloc[0] == pytest.approx(100 * 0.8)
    assert gens["peaking_1"].marginal_cost.iloc[0] == pytest.approx(gas_fuel / 0.35)


def test_adjustments_change_costs_and_capacity(tmp_path: Path) -> None:
    inputs = write_inputs(tmp_path)
    adjustments = Adjustments(
        capacity_mw={"coal": 0.0},
        fuel_price_scale={"gas": 2.0},
        eu_ets_gbp_per_t=0.0,
        carbon_price_support=False,
    )
    gens = {g.name: g for g in thermal_generators(INDEX, inputs, None, adjustments)}
    assert gens["coal_1"].capacity_mw.sum() == 0.0
    assert gens["ccgt_3"].marginal_cost.iloc[0] == pytest.approx(40.0 / 0.5)


def test_one_year_at_a_time(tmp_path: Path) -> None:
    inputs = write_inputs(tmp_path)
    index = pd.DatetimeIndex(["2018-12-31 23:00", "2019-01-01"], tz="UTC")
    with pytest.raises(DataError, match="one calendar year"):
        thermal_generators(index, inputs)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"tranches": 0}, "tranches"),
        ({"availability": 0.0}, "availability"),
        ({"ccgt_spread": 0.3}, "ccgt_spread"),
        ({"peaking_efficiency": 1.2}, "peaking_efficiency"),
        ({"variable_cost": -1.0}, "variable_cost"),
    ],
)
def test_assumption_validation(kwargs: dict[str, float], match: str) -> None:
    with pytest.raises(ConfigError, match=match):
        FleetAssumptions(**kwargs)  # type: ignore[arg-type]


def test_adjustment_validation() -> None:
    with pytest.raises(ConfigError, match="unknown keys tidal"):
        Adjustments(scale={"tidal": 2.0})
    with pytest.raises(ConfigError, match=r"capacity_mw\.coal"):
        Adjustments(capacity_mw={"coal": -1.0})
    with pytest.raises(ConfigError, match="eu_ets"):
        Adjustments(eu_ets_gbp_per_t=float("nan"))


def bundled_mix(start: date, end: date) -> pd.DataFrame:
    source = GenerationMixSource(BUNDLED / "generation_mix.csv")
    return source.mix(start, end, step=pd.Timedelta(hours=1))


def test_bundled_system_balances_and_matches_history() -> None:
    mix = bundled_mix(date(2019, 6, 1), date(2019, 6, 7))
    spec = build_system(mix, SystemInputs(BUNDLED))
    result = solve(spec)
    supplied = result.generation.sum(axis=1) + result.unserved
    assert np.allclose(supplied, mix["generation"])
    by_tech = result.by_technology()
    assert np.allclose(by_tech["nuclear"], mix["nuclear"])
    assert np.allclose(by_tech["pumped_storage"], mix["storage"])
    assert result.curtailment.sum() == pytest.approx(0.0)
    thermal = by_tech[["ccgt", "coal", "peaking"]].sum(axis=1)
    # NESO's total can differ from the sum of its rounded fuels by a few MW.
    assert np.allclose(thermal, mix["gas"] + mix["coal"], atol=5.0)
    assert result.unserved.sum() == 0
    assert 20 < result.price.mean() < 80


def test_scaling_renewables_curtails_and_cuts_price() -> None:
    mix = bundled_mix(date(2019, 6, 1), date(2019, 6, 7))
    inputs = SystemInputs(BUNDLED)
    base = solve(build_system(mix, inputs))
    more = solve(build_system(mix, inputs, adjustments=Adjustments(scale={"wind": 4.0})))
    assert more.curtailment.sum() > 0
    assert more.price.mean() < base.price.mean()
    assert more.emissions_t.sum() < base.emissions_t.sum()
    with pytest.raises(DataError, match="must-run"):
        solve(build_system(mix, inputs, adjustments=Adjustments(scale={"nuclear": 6.0})))


def test_build_system_rejects_gaps() -> None:
    mix = bundled_mix(date(2019, 6, 1), date(2019, 6, 1))
    mix.iloc[3, 0] = np.nan
    with pytest.raises(DataError, match="missing"):
        build_system(mix, SystemInputs(BUNDLED))
