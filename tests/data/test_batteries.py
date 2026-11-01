from pathlib import Path

import pandas as pd
import pytest

from openenergy.data.batteries import DAILY_COLUMNS, RealBatteries
from openenergy.errors import DataError

BUNDLED = Path(__file__).parents[2] / "data/fleet"


def write(directory: Path) -> Path:
    pd.DataFrame(
        {
            "unit": ["E_AB-1", "T_CD-1"],
            "name": ["A Battery", "C BESS"],
            "generation_capacity_mw": [50.0, 100.0],
            "gsp_group": ["Eastern", ""],
            "zone": ["england_wales", "scotland"],
        }
    ).to_csv(directory / "battery_units.csv", index=False)
    rows = []
    for day in pd.date_range("2024-12-31", "2025-01-02"):
        for unit in ("E_AB-1", "T_CD-1"):
            row = {
                "date": day.strftime("%Y-%m-%d"),
                "unit": unit,
                **dict.fromkeys(DAILY_COLUMNS, 0.0),
            }
            row.update(
                metered_mwh_out=40.0, metered_mwh_in=50.0, metered_value_day_ahead_gbp=1000.0
            )
            row.update(bm_offer_gbp=300.0, bm_bid_gbp=-100.0)
            rows.append(row)
    pd.DataFrame(rows).to_csv(directory / "battery_daily.csv", index=False)
    pd.DataFrame(
        {
            "utc_timestamp": ["2025-01-01T00:00:00Z"],
            "metered_net_mw": [-20.0],
            "pn_net_mw": [5.0],
            "units": [2],
        }
    ).to_csv(directory / "fleet_hourly.csv", index=False)
    return directory


def test_by_year_scales_by_registered_capacity_and_days(tmp_path: Path) -> None:
    years = RealBatteries(write(tmp_path)).by_year()
    assert list(years.index) == [2024, 2025]
    y2025 = years.loc[2025]
    assert y2025["units"] == 2
    assert y2025["mw_years"] == pytest.approx(2 * 150 / 365)
    assert y2025["metered_value_day_ahead_per_mw_year"] == pytest.approx(4 * 1000 / (300 / 365))
    assert y2025["bm_net_per_mw_year"] == pytest.approx(4 * 200 / (300 / 365))
    assert y2025["round_trip"] == pytest.approx(0.8)


def test_by_zone_splits_units(tmp_path: Path) -> None:
    zones = RealBatteries(write(tmp_path)).by_year(by_zone=True)
    assert zones.loc[(2025, "scotland"), "mw_years"] == pytest.approx(2 * 100 / 365)
    assert zones.loc[(2025, "england_wales"), "units"] == 1


def test_hourly_reads_utc(tmp_path: Path) -> None:
    hourly = RealBatteries(write(tmp_path)).hourly()
    assert hourly.index[0] == pd.Timestamp("2025-01-01", tz="UTC")
    assert hourly["metered_net_mw"].iloc[0] == -20.0


def test_missing_files_and_units_are_errors(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="not found"):
        RealBatteries(tmp_path).daily()
    write(tmp_path)
    units = pd.read_csv(tmp_path / "battery_units.csv").iloc[:1]
    units.to_csv(tmp_path / "battery_units.csv", index=False)
    with pytest.raises(DataError, match="T_CD-1"):
        RealBatteries(tmp_path).by_year()


@pytest.mark.skipif(not (BUNDLED / "battery_daily.csv").is_file(), reason="fleet data not built")
def test_bundled_fleet_balances_energy() -> None:
    years = RealBatteries(BUNDLED).by_year().loc[2023:]
    # Batteries lose energy each cycle: the fleet imports more than it exports, but not far
    # more (2021-2022, a few units mostly in frequency response, metered 67-69%).
    assert ((years["round_trip"] > 0.75) & (years["round_trip"] < 0.95)).all()
