from pathlib import Path

import pandas as pd
import pytest

from openenergy import ConfigError, DataError
from openenergy.data.fes import FesSource
from openenergy.data.interconnectors import GAP_EDGES, gap_shares
from openenergy.system.forward import fes_changes, links

ROOT = Path(__file__).parents[2]
FES = FesSource(ROOT / "data/fes")
THERMAL = {"ccgt": 30000.0, "peaking": 2000.0}


def test_fes_tables() -> None:
    capacity = FES.capacity_mw("Holistic Transition", 2030)
    assert capacity["Battery"] == pytest.approx(23169, abs=1)
    assert capacity["Interconnectors"] == pytest.approx(11700)
    assert FES.storage_gwh("Holistic Transition", 2030)["Battery"] == pytest.approx(33.75, 0.01)
    assert FES.demand_gwh("Holistic Transition", 2030) == pytest.approx(339295)
    assert FES.years("Ten Year Outlook")[0] == 2025
    assert FES.years("Holistic Transition")[0] == 2024


def test_fes_errors(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="unknown FES pathway"):
        FES.capacity_mw("Net Zero", 2030)
    with pytest.raises(DataError, match="no 2060 column"):
        FES.capacity_mw("Ten Year Outlook", 2060)
    with pytest.raises(DataError, match="not found"):
        FesSource(tmp_path).capacity_mw("Holistic Transition", 2030)


def changes(pathway: str = "Holistic Transition", year: int = 2030, base: int = 2025):
    return fes_changes(FES, pathway, year, base, THERMAL, 0.85, 0.75)


def test_fes_changes_scale_from_the_weather_year() -> None:
    result = changes()
    target = FES.capacity_mw("Holistic Transition", 2030)
    base = FES.capacity_mw("Holistic Transition", 2025)
    wind = ["Offshore Wind", "Onshore Wind"]
    assert result.scale["wind"] == pytest.approx(target[wind].sum() / base[wind].sum())
    assert result.scale["demand"] == pytest.approx(
        FES.demand_gwh("Holistic Transition", 2030) / FES.demand_gwh("Holistic Transition", 2025)
    )
    assert result.capacity_mw["coal"] == 0
    gas = ["Gas", "CCS Gas", "Hydrogen"]
    ratio = target[gas].sum() / base[gas].sum()
    assert result.capacity_mw["ccgt"] == pytest.approx(30000 * ratio)
    assert result.link_scale == pytest.approx(target["Interconnectors"] / base["Interconnectors"])
    battery, ldes = result.storage
    assert battery.name == "fes_battery" and battery.power_mw == pytest.approx(23169, abs=1)
    assert battery.hours == pytest.approx(33.75 / 23.169, rel=1e-3)
    assert ldes.name == "fes_long_duration" and ldes.efficiency == 0.75


def test_same_year_changes_nothing_but_adds_batteries() -> None:
    result = changes(year=2025)
    assert all(value == pytest.approx(1.0) for value in result.scale.values())
    assert [unit.name for unit in result.storage] == ["fes_battery"]


def test_fes_year_bounds() -> None:
    with pytest.raises(ConfigError, match="2025 to 2035"):
        changes(year=2040)
    with pytest.raises(ConfigError, match="before the weather year"):
        changes(year=2025, base=2026)


def test_links_follow_in_service_dates() -> None:
    index = pd.date_range("2023-12-28", periods=48, freq="1h", tz="UTC")
    built = {
        link.name: link
        for link in links(
            index,
            ROOT / "data/system",
            ROOT / "data/prices/europe_day_ahead_ember.csv",
            scale=2.0,
            hurdle=3.0,
            availability=0.5,
        )
    }
    assert "Greenlink" not in built  # in service 2025
    viking = built["Viking Link Denmark Interconnector"]
    assert viking.import_mw.iloc[0] == 0  # 28 December
    assert viking.import_mw.iloc[-1] == pytest.approx(1500.0)  # 29 December: 1500 x 2 x 0.5
    assert viking.hurdle == 3.0
    assert built["IFA Interconnector"].price.notna().all()


def test_links_use_availability_fitted_from_flows(tmp_path: Path) -> None:
    index = pd.date_range("2024-06-01", periods=2, freq="1h", tz="UTC")
    prices = ROOT / "data/prices/europe_day_ahead_ember.csv"
    built = {link.name: link for link in links(index, ROOT / "data/system", prices)}
    fitted = pd.read_csv(ROOT / "data/system/interconnector_availability.csv").set_index("link")
    register = pd.read_csv(ROOT / "data/system/interconnectors.csv").set_index("link")
    ifa, name = built["IFA Interconnector"], "IFA Interconnector"
    assert ifa.import_mw.iloc[0] == pytest.approx(
        register.loc[name, "import_mw"] * fitted.loc[name, "import_availability"]
    )
    assert ifa.export_mw.iloc[0] == pytest.approx(
        register.loc[name, "export_mw"] * fitted.loc[name, "export_availability"]
    )
    for file in ("interconnectors.csv", "interconnector_flows.csv"):
        (tmp_path / file).write_bytes((ROOT / "data/system" / file).read_bytes())
    with pytest.raises(DataError, match="interconnector_availability"):
        links(index, tmp_path, prices)
    assert links(index, tmp_path, prices, availability=1.0)
    with pytest.raises(DataError, match="interconnector_gap_availability"):
        links(index, tmp_path, prices, availability="gap")


def test_gap_availability_offers_each_link_in_steps() -> None:
    index = pd.date_range("2024-06-01", periods=2, freq="1h", tz="UTC")
    prices = ROOT / "data/prices/europe_day_ahead_ember.csv"
    steps = links(index, ROOT / "data/system", prices, scale=2.0, hurdle=1.0, availability="gap")
    ifa = [link for link in steps if link.name.startswith("IFA Interconnector (")]
    assert [link.name for link in ifa] == [
        f"IFA Interconnector (gap from £{edge:g})" for edge in GAP_EDGES
    ]
    assert [link.hurdle for link in ifa] == [1.0 + edge for edge in GAP_EDGES]
    imports, exports = gap_shares(ROOT / "data/system")["IFA Interconnector"]
    assert sum(link.import_mw.iloc[0] for link in ifa) == pytest.approx(2.0 * 1988 * imports[-1])
    assert ifa[1].import_mw.iloc[0] == pytest.approx(2.0 * 1988 * (imports[1] - imports[0]))
    assert all((link.export_mw >= 0).all() for link in ifa)
    assert sum(link.export_mw.iloc[0] for link in ifa) > 0
    assert exports[-1] >= exports[0]
