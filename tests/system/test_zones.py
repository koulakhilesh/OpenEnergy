import dataclasses
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from openenergy import ConfigError, DataError
from openenergy.data.fleet import SystemInputs
from openenergy.data.neso import GenerationMixSource
from openenergy.system.fleet import build_system
from openenergy.system.model import Storage
from openenergy.system.zones import (
    boundary_limit,
    compare,
    scottish_shares,
    solve_two_zones,
)

ROOT = Path(__file__).parents[2]
ZONES = ROOT / "data/zones"


def week(first: date, last: date):
    mix = GenerationMixSource(ROOT / "data/system/generation_mix.csv").mix(
        first, last, step=pd.Timedelta(hours=1)
    )
    return build_system(mix, SystemInputs(ROOT / "data/system"))


def test_scottish_shares_from_dukes_and_repd() -> None:
    shares = scottish_shares(ZONES, 2024)
    assert 0.35 < shares["wind"] < 0.55
    assert shares["hydro"] > 0.85
    assert shares["coal"] == 0 and shares["imports"] == 0
    assert all(0 <= value <= 1 for value in shares.values())


def test_boundary_limits() -> None:
    index = pd.date_range("2024-03-01", periods=48, freq="h", tz="UTC")
    scotex = boundary_limit(ZONES, index, "scotex")
    monthly = pd.read_csv(ROOT / "data/constraints/day_ahead_boundaries_monthly.csv")
    march = monthly[(monthly["group"] == "SCOTEX") & (monthly["month"] == "2024-03")]
    assert scotex.iloc[0] == pytest.approx(float(march["limit_mw"].iloc[0]))
    assert boundary_limit(ZONES, index, 3000.0).eq(3000.0).all()
    assert boundary_limit(ZONES, index, "recorded").iloc[0] > 0
    with pytest.raises(ConfigError, match="positive"):
        boundary_limit(ZONES, index, 0.0)
    early = pd.date_range("2020-03-01", periods=24, freq="h", tz="UTC")
    with pytest.raises(DataError, match="no SCOTEX limit"):
        boundary_limit(ZONES, early, "scotex")


def test_two_zones_respect_the_boundary_and_split_prices() -> None:
    spec = week(date(2024, 1, 15), date(2024, 1, 21))
    result = solve_two_zones(spec, ZONES, 2000.0)
    frame = result.frame
    assert (frame["transfer_model_mw"].abs() <= 2000.0 + 1e-6).all()
    exporting = frame["transfer_model_mw"] >= 2000.0 - 1e-6
    assert exporting.any()
    gap = frame["price_england_wales"] - frame["price_scotland"]
    assert (gap[exporting] >= -1e-6).all()
    unconstrained = solve_two_zones(spec, ZONES, 50000.0).frame
    assert np.allclose(unconstrained["price_scotland"], unconstrained["price_england_wales"])
    summary = compare(result)
    assert summary["model_at_limit_share"] == pytest.approx(exporting.mean(), abs=0.05)
    assert -1 <= summary["correlation"] <= 1


def test_two_zones_need_the_historic_system() -> None:
    spec = week(date(2024, 1, 15), date(2024, 1, 16))
    stored = dataclasses.replace(spec, storage=(Storage("battery", 100.0, 2.0, 0.9),))
    with pytest.raises(ConfigError, match="no storage or links"):
        solve_two_zones(stored, ZONES)
