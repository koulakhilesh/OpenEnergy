from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from openenergy import ConfigError
from openenergy.cli import app
from openenergy.system import absorb_surplus, sizing_grid


def hourly(values: list[float]) -> pd.Series:
    index = pd.date_range("2019-01-01", periods=len(values), freq="h", tz="UTC")
    return pd.Series(values, index=index, dtype=float)


def test_absorbs_and_releases_by_hand() -> None:
    fleet = absorb_surplus(
        hourly([-10, -10, 20, 20]), power_mw=5, hours=2, eta_charge=1, eta_discharge=1
    )
    assert fleet.energy_mwh == 10
    assert fleet.surplus_mwh == 20
    assert fleet.absorbed_mwh == 10
    assert fleet.absorbed_share == pytest.approx(0.5)
    assert fleet.released_mwh == 10
    assert fleet.equivalent_cycles == pytest.approx(1.0)


def test_energy_capacity_binds() -> None:
    fleet = absorb_surplus(
        hourly([-10, -10, 20]), power_mw=20, hours=0.25, eta_charge=1, eta_discharge=1
    )
    assert fleet.absorbed_mwh == pytest.approx(5.0)


def test_efficiency_losses() -> None:
    fleet = absorb_surplus(
        hourly([-10, 50]), power_mw=10, hours=4, eta_charge=0.9, eta_discharge=0.8
    )
    assert fleet.absorbed_mwh == pytest.approx(10.0)
    assert fleet.released_mwh == pytest.approx(10 * 0.9 * 0.8)


def test_release_does_not_push_net_load_below_floor() -> None:
    fleet = absorb_surplus(
        hourly([-10, 2, 30]), power_mw=50, hours=1, eta_charge=1, eta_discharge=1
    )
    assert fleet.released_mwh == pytest.approx(10.0)
    assert fleet.residual.tolist() == pytest.approx([0.0, 0.0, 22.0])


def test_must_run_floor_moves_surplus() -> None:
    fleet = absorb_surplus(
        hourly([5, 15]), power_mw=10, hours=1, must_run_mw=10, eta_charge=1, eta_discharge=1
    )
    assert fleet.surplus_mwh == pytest.approx(5.0)
    assert fleet.released_mwh == pytest.approx(5.0)


def test_missing_hours_are_idle() -> None:
    fleet = absorb_surplus(
        hourly([-10, np.nan, 20]), power_mw=10, hours=1, eta_charge=1, eta_discharge=1
    )
    assert fleet.absorbed_mwh == pytest.approx(10.0)
    assert np.isnan(fleet.residual.iloc[1])


def test_no_surplus_gives_zero_share() -> None:
    fleet = absorb_surplus(hourly([10, 20]), power_mw=1, hours=1)
    assert fleet.absorbed_share == 0.0


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"power_mw": 0, "hours": 1}, "power_mw"),
        ({"power_mw": 1, "hours": -1}, "hours"),
        ({"power_mw": 1, "hours": 1, "eta_charge": 1.5}, "eta_charge"),
    ],
)
def test_validation(kwargs: dict[str, float], message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        absorb_surplus(hourly([-1, 1]), **kwargs)


def test_sizing_grid_shows_diminishing_returns() -> None:
    rng = np.random.default_rng(0)
    net = hourly(list(rng.normal(5, 10, 24 * 30)))
    grid = sizing_grid(net, powers_mw=[1, 5, 20], hours=[1, 4])
    assert list(grid.columns) == [
        "power_mw",
        "hours",
        "energy_mwh",
        "absorbed_share",
        "absorbed_mwh",
        "released_mwh",
        "equivalent_cycles",
    ]
    assert len(grid) == 6
    by_power = grid[grid["hours"] == 4].set_index("power_mw")["absorbed_share"]
    assert by_power[1] < by_power[5] <= by_power[20]


def write_opsd(path: Path) -> Path:
    hours = 24 * 10
    index = pd.date_range("2019-01-01", periods=hours, freq="h", tz="UTC")
    hour = np.arange(hours) % 24
    pd.DataFrame(
        {
            "utc_timestamp": index.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "GB_GBN_price_day_ahead": 50.0,
            "GB_GBN_load_actual_entsoe_transparency": 25000
            + 5000 * np.sin((hour - 6) * np.pi / 12),
            "GB_GBN_wind_generation_actual": 8000.0,
            "GB_GBN_solar_generation_actual": np.clip(np.sin((hour - 6) * np.pi / 12), 0, None)
            * 6000,
        }
    ).to_csv(path, index=False)
    return path


def test_cli_storage(tmp_path: Path) -> None:
    path = write_opsd(tmp_path / "ts.csv")
    result = CliRunner().invoke(
        app,
        [
            "storage",
            str(path),
            "--scale-wind",
            "2",
            "--scale-solar",
            "3",
            "--power",
            "1000,5000",
            "--hours",
            "2,8",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "surplus" in result.output.splitlines()[0]
    assert "8h" in result.output
