import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

import openenergy
from openenergy.cli import app
from openenergy.report import build_report, load_output

runner = CliRunner()


def test_report_has_every_section_and_matches_the_summary(
    battery_dir: Path, system_dir: Path, backcast_dir: Path, sweep_csv: Path
) -> None:
    outputs = [load_output(p) for p in (battery_dir, system_dir, backcast_dir, sweep_csv)]
    page = build_report(outputs, title="Test report")
    assert page.startswith("<!DOCTYPE html>") and page.count("<section") == 4
    assert f"OpenEnergy {openenergy.__version__}" in page
    summary = json.loads((battery_dir / "summary.json").read_text())["summary"]
    assert f"{summary['revenue']:,.0f}" in page
    assert f"{summary['capture_ratio']:.1%}" in page
    assert "Open Power System Data" in page and "CC BY 4.0" in page
    assert page.count("plotly.js v") <= 2  # library inlined once
    assert "Mean price by hour" in page and "Generation by month" in page
    assert "Sweep results, best first" in page


def test_comparisons_and_cdn(battery_dir: Path, system_dir: Path) -> None:
    runs = [load_output(battery_dir), load_output(battery_dir)]
    systems = [load_output(system_dir), load_output(system_dir)]
    page = build_report([*runs, *systems], cdn=True)
    assert "Battery comparison" in page and "System comparison" in page
    assert "cdn.plot.ly" in page
    assert len(page) < 2_000_000
    assert len(build_report(runs[:1])) > 4_000_000


def test_text_from_files_is_escaped(battery_dir: Path) -> None:
    summary_path = battery_dir / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["scenario"] = "<script>alert(1)</script>"
    summary["note"] = "<img src=x onerror=alert(1)>"
    summary_path.write_text(json.dumps(summary))
    page = build_report([load_output(battery_dir)], title="<b>t</b>")
    assert "<script>alert(1)</script>" not in page
    assert "<img src=x" not in page and "<b>t</b>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_site_battery_sections(battery_dir: Path) -> None:
    daily = pd.read_csv(battery_dir / "daily.csv")
    daily["available_mwh"] = 10.0
    daily["curtailed_mwh"] = 1.0
    daily["emissions_t"] = -0.5
    daily.to_csv(battery_dir / "daily.csv", index=False)
    (battery_dir / "benchmark_daily.csv").unlink()
    summary_path = battery_dir / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["summary"].update(premium=12.5, curtailed_mwh=3.0, emissions_t=-7.0)
    summary["carbon_attribution"] = "Carbon intensity: NESO, CC BY 4.0"
    summary_path.write_text(json.dumps(summary))
    page = build_report([load_output(battery_dir)], cdn=True)
    assert "Plant output by month" in page and "Net emissions" in page
    assert "Premium (GBP)" in page and "Curtailed (MWh)" in page
    assert "Carbon intensity: NESO" in page
    assert "perfect foresight" not in page.split("Cumulative revenue")[0][-200:]


def test_stacked_battery_section(battery_dir: Path) -> None:
    daily = pd.read_csv(battery_dir / "daily.csv")
    daily["energy_revenue"] = daily["revenue"] - 1.0
    daily["response_revenue"] = 1.0
    daily.to_csv(battery_dir / "daily.csv", index=False)
    summary_path = battery_dir / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["summary"]["response_revenue"] = 14.0
    summary["response_attribution"] = "Frequency response: NESO"
    summary["response_note"] = "price-taker"
    summary_path.write_text(json.dumps(summary))
    page = build_report([load_output(battery_dir)], cdn=True)
    assert "Revenue by market" in page and "of which frequency response (GBP)" in page
    assert "Frequency response: NESO" in page and "price-taker" in page


def test_system_with_battery_and_start_price(system_dir: Path) -> None:
    summary_path = system_dir / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["battery"] = {"revenue_per_mw_year": 1234.0, "capture_ratio": 0.5}
    summary_path.write_text(json.dumps(summary))
    dispatch = pd.read_csv(system_dir / "dispatch.csv")
    dispatch.insert(2, "start_price", dispatch["price"] + 5)
    dispatch.to_csv(system_dir / "dispatch.csv", index=False)
    page = build_report([load_output(system_dir)], cdn=True)
    assert "1,234" in page and "50.0%" in page
    assert '"name":"start price"' in page


def test_no_outputs_is_an_error() -> None:
    with pytest.raises(ValueError, match="no outputs"):
        build_report([])


def test_cli_report(battery_dir: Path, sweep_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "out" / "r.html"
    result = runner.invoke(
        app, ["report", str(battery_dir), str(sweep_csv), "-o", str(out), "--cdn"]
    )
    assert result.exit_code == 0, result.output
    assert out.is_file() and "2 output(s)" in result.output
    missing = runner.invoke(app, ["report", str(tmp_path / "nope")])
    assert missing.exit_code == 1 and "no output directory" in missing.output
