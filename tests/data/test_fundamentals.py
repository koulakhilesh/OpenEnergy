import io
import json
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from openenergy.cli import app
from openenergy.data import FUNDAMENTALS_ATTRIBUTION, FundamentalsSource
from openenergy.data import update as update_module
from openenergy.data.fundamentals import decisions
from openenergy.data.update import update_fundamentals
from openenergy.errors import DataError

ROOT = Path(__file__).parents[2]
runner = CliRunner()
ONS_PAGE = (
    '<a href="/file?uri=/economy/x/systemaveragepricesapofgas/current/sap.xlsx">current</a>'
    '<a href="/file?uri=/economy/x/systemaveragepricesapofgas/2026/sap291026.xlsx">2026</a>'
    '<a href="/file?uri=/economy/x/systemaveragepricesapofgas/2025/sap181225.xlsx">2025</a>'
)
NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def sap_workbook() -> bytes:
    """A two-sheet workbook laid out like ONS's: a title, a header row, then daily rows."""
    strings = ["Table 1: Daily SAP", "Date", "SAP actual day", "[x]"]

    def cell(ref: str, value: str, text: bool = False) -> str:
        if text:
            return f'<c r="{ref}" t="s"><v>{strings.index(value)}</v></c>'
        return f'<c r="{ref}"><v>{value}</v></c>'

    rows = [
        f'<row r="1">{cell("A1", "Table 1: Daily SAP", True)}</row>',
        f'<row r="2">{cell("A2", "Date", True)}{cell("B2", "SAP actual day", True)}</row>',
        f'<row r="3">{cell("A3", "43101")}{cell("B3", "1.7083")}</row>',  # 2018-01-01
        f'<row r="4">{cell("A4", "43102")}{cell("B4", "[x]", True)}</row>',
        f'<row r="5">{cell("A5", "43103")}{cell("B5", "2.5")}</row>',
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr(
            "xl/workbook.xml",
            f'<workbook {NS} {R}><sheets><sheet name="Cover" sheetId="1" r:id="rId1"/>'
            f'<sheet name="1.Daily SAP Gas" sheetId="2" r:id="rId2"/></sheets></workbook>',
        )
        book.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Target="/xl/worksheets/sheet2.xml"/></Relationships>',
        )
        book.writestr("xl/worksheets/sheet1.xml", f"<worksheet {NS}><sheetData/></worksheet>")
        book.writestr(
            "xl/worksheets/sheet2.xml",
            f"<worksheet {NS}><sheetData>{''.join(rows)}</sheetData></worksheet>",
        )
        sst = "".join(f"<si><t>{s}</t></si>" for s in strings)
        book.writestr("xl/sharedStrings.xml", f"<sst {NS}>{sst}</sst>")
    return buffer.getvalue()


DEMAND_CSV = (
    "DAYSAHEAD,TARGETDATE,FORECASTDEMAND,CARDINALPOINT,CP_TYPE,CP_ST_TIME,CP_END_TIME,"
    "F_Point,FORECAST_TIMESTAMP\n"
    '1,"2024-07-02",20000,"1F","F",100,100,NA,"2024-07-01T08:45:00Z"\n'
    '1,"2024-07-02",30000,"3B","P",1800,1830,NA,"2024-07-01T08:45:00Z"\n'
    '2,"2024-07-03",99999,"1F","F",100,100,NA,"2024-07-01T08:45:00Z"\n'
)


def windfor(month: str) -> list[dict[str, object]]:
    if month != "2024-07":
        return []

    def row(issued: str, hour: int, mw: int) -> dict[str, object]:
        start = f"2024-07-02T{hour:02d}:00:00Z"
        return {"publishTime": f"2024-07-01T{issued}:00Z", "startTime": start, "generation": mw}

    return [
        row("09:30", 10, 5000),  # issued the morning before: kept
        row("11:30", 10, 5100),  # a later issue still before noon replaces it
        row("15:30", 11, 9999),  # issued after the decision: dropped
        row("09:30", 11, 4000),
    ]


def fake_download(url: str) -> bytes:
    if url == update_module.ONS_SAP:
        return ONS_PAGE.encode()
    if url.endswith("/2026/sap291026.xlsx"):
        return sap_workbook()
    if url.startswith("https://api.neso.energy/api/3/action/datapackage_show"):
        resources = [{"name": "historic_day_ahead_demand_forecasts", "path": "neso://demand"}]
        return json.dumps({"result": {"resources": resources}}).encode()
    if url == "neso://demand":
        return DEMAND_CSV.encode()
    if url.startswith("https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream"):
        month = url.split("publishDateTimeFrom=")[1][:7]
        return json.dumps(windfor(month)).encode()
    raise AssertionError(url)


def test_update_fundamentals_writes_what_the_source_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(update_module, "_download", fake_download)
    monkeypatch.setattr(update_module, "WINDFOR_FROM", date(2024, 6, 1))
    written = update_fundamentals(tmp_path, date(2024, 7, 31))
    assert [w[:2] for w in written] == [
        ("gas_sap_daily.csv", 2),
        ("neso_demand_day_ahead.csv", 2),
        ("elexon_wind_day_ahead.csv", 2),
    ]
    source = FundamentalsSource(tmp_path)
    gas = source.gas_daily()
    assert gas.index[0] == pd.Timestamp("2018-01-01", tz="UTC")
    assert gas.tolist() == pytest.approx([17.083, 25.0])
    hours = pd.DatetimeIndex(["2024-07-02 10:00", "2024-07-02 11:00"], tz="UTC")
    assert source.wind(hours, decisions(hours, 12)).tolist() == [5100.0, 4000.0]
    demand = pd.read_csv(tmp_path / "neso_demand_day_ahead.csv")
    # 01:00 and 18:15 BST are 00:00 and 17:15 UTC.
    assert demand["target_utc"].tolist() == ["2024-07-02T00:00:00Z", "2024-07-02T17:15:00Z"]


def test_cli_downloads_fundamentals_beside_prices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    monkeypatch.setattr("openenergy.cli.update_prices", lambda d: (d / "p.csv", 2, "a", "b"))

    def fundamentals(directory: Path) -> list[tuple[str, int, str, str]]:
        calls.append(directory)
        return [("gas_sap_daily.csv", 3, "2018-01-01", "2018-01-03")]

    monkeypatch.setattr("openenergy.cli.update_fundamentals", fundamentals)
    result = runner.invoke(app, ["data", "update", "--dir", str(tmp_path / "prices")])
    assert result.exit_code == 0 and not calls
    result = runner.invoke(
        app, ["data", "update", "--dir", str(tmp_path / "prices"), "--fundamentals"]
    )
    assert result.exit_code == 0, result.output
    assert calls == [tmp_path / "fundamentals"]
    assert "gas_sap_daily.csv: 3 rows" in result.output and "ONS" not in result.output
    assert "Open Government Licence" in result.output


def write_fundamentals(directory: Path) -> FundamentalsSource:
    pd.DataFrame({"date": ["2024-07-01", "2024-07-02"], "sap_p_per_kwh": [3.0, 4.0]}).to_csv(
        directory / "gas_sap_daily.csv", index=False
    )
    pd.DataFrame(
        {
            "target_utc": ["2024-07-02T00:00:00Z", "2024-07-02T04:00:00Z", "2024-07-02T04:00:00Z"],
            "demand_mw": [20000, 24000, 99999],
            "issued_utc": ["2024-07-01T08:45:00Z", "2024-07-01T08:45:00Z", "2024-07-01T13:00:00Z"],
        }
    ).to_csv(directory / "neso_demand_day_ahead.csv", index=False)
    pd.DataFrame(
        {
            "target_utc": ["2024-07-02T01:00:00Z"],
            "wind_mw": [7000],
            "issued_utc": ["2024-07-01T11:30:00Z"],
        }
    ).to_csv(directory / "elexon_wind_day_ahead.csv", index=False)
    return FundamentalsSource(directory)


def test_forecasts_are_only_those_issued_by_the_decision(tmp_path: Path) -> None:
    source = write_fundamentals(tmp_path)
    hours = pd.date_range("2024-07-02 00:00", periods=6, freq="h", tz="UTC")
    demand = source.demand(hours, decisions(hours, 12))
    # The 13:00 issue came after noon the day before, so 04:00 keeps the earlier 24,000.
    assert demand[:5].tolist() == pytest.approx([20000, 21000, 22000, 23000, 24000])
    assert np.isnan(demand[5])
    assert np.isnan(source.demand(hours, decisions(hours, 36))).all()  # nothing that early
    later = source.demand(hours, decisions(hours, 10))
    assert later[4] == 99999 and later[2] == pytest.approx(20000 + 2 / 4 * 79999)
    wind = source.wind(hours, decisions(hours, 12))
    assert wind[1] == 7000 and np.isnan(wind[0])
    assert np.isnan(source.wind(hours, decisions(hours, 13))[1])
    # A plan for two days made at one time sees only what was issued by then.
    two_days = pd.date_range("2024-07-01 00:00", periods=48, freq="h", tz="UTC")
    once = pd.DatetimeIndex([pd.Timestamp("2024-06-30 12:00", tz="UTC")] * 48)
    assert np.isnan(source.wind(two_days, once)).all()


def test_gas_by_day_with_a_lag(tmp_path: Path) -> None:
    source = write_fundamentals(tmp_path)
    hours = pd.DatetimeIndex(["2024-07-02 00:00", "2024-07-02 23:00", "2024-07-03 01:00"], tz="UTC")
    assert source.gas(hours).tolist()[:2] == pytest.approx([40.0, 40.0])
    assert np.isnan(source.gas(hours)[2])
    assert source.gas(hours, lag_days=1).tolist() == pytest.approx([30.0, 30.0, 40.0])


def test_missing_files_and_columns(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="fetch_fundamentals"):
        FundamentalsSource(tmp_path).gas_daily()
    pd.DataFrame({"date": ["2024-07-01"]}).to_csv(tmp_path / "gas_sap_daily.csv", index=False)
    with pytest.raises(DataError, match="sap_p_per_kwh"):
        FundamentalsSource(tmp_path).gas_daily()


def test_bundled_fundamentals_cover_the_forecast_years() -> None:
    source = FundamentalsSource(ROOT / "data/fundamentals")
    hours = pd.date_range("2020-01-01", "2026-10-28 23:00", freq="h", tz="UTC")
    known = decisions(hours, 12)
    assert np.isfinite(source.demand(hours, known)).mean() > 0.99
    assert np.isfinite(source.wind(hours, known)).mean() > 0.99
    gas = source.gas_daily()
    assert gas.index[0] == pd.Timestamp("2018-01-01", tz="UTC")
    assert gas.loc["2022-08-29"] == pytest.approx(193.89)
    assert "Open Government Licence" in FUNDAMENTALS_ATTRIBUTION
    assert "Supported by National Energy SO Open Data" in FUNDAMENTALS_ATTRIBUTION
    assert "Elexon" in FUNDAMENTALS_ATTRIBUTION
