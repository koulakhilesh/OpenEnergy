"""Download NESO Future Energy Scenarios tables and the interconnector register.

Sources (National Energy System Operator, NESO Open Data Licence v1.0,
https://www.neso.energy/data-portal/neso-open-licence; supported by National Energy SO
Open Data; OpenEnergy is not affiliated with or endorsed by NESO):

- FES: Pathways to Net Zero, Electricity Supply Data Table (ES1),
  https://www.neso.energy/data-portal/future-energy-scenario-electricity-supply-data-table-es1
- FES: Pathways to Net Zero, Electricity Demand Summary Data table (ED1),
  https://www.neso.energy/data-portal/fes-electricity-demand-summary-data-table-ed1
- Interconnector Register, https://www.neso.energy/data-portal/interconnector-register

Writes the FES 2025 tables and the 2026 Ten Year Outlook tables to data/fes/ unchanged,
and the built interconnectors from the register to data/system/interconnectors.csv with
the neighbouring market each one reaches.

Run: uv run python scripts/fetch_fes.py
"""

import csv
import io
import json
from pathlib import Path

from openenergy.data.update import _download

ROOT = Path(__file__).parents[1]
API = "https://api.neso.energy/api/3/action/datapackage_show?id={}"
TABLES = {
    "future-energy-scenario-electricity-supply-data-table-es1": {
        "electricity_supply_data_table_(es1)_2025": "fes2025_es1.csv",
        "electricity_supply_data_table_(es1)_2026": "tyo2026_es1.csv",
    },
    "fes-electricity-demand-summary-data-table-ed1": {
        "electricity_demand_summary_(ed1)_2025": "fes2025_ed1.csv",
        "electricity_demand_summary_(ed1)_2026": "tyo2026_ed1.csv",
    },
}
# Register project name -> (neighbouring market as in europe_day_ahead_ember.csv, BMRS fuel type).
LINKS = {
    "IFA Interconnector": ("france", "INTFR"),
    "IFA2 Interconnector": ("france", "INTIFA2"),
    "ElecLink": ("france", "INTELEC"),
    "Britned": ("netherlands", "INTNED"),
    "Nemo Link": ("belgium", "INTNEM"),
    "NS Link": ("norway", "INTNSL"),
    "Viking Link Denmark Interconnector": ("denmark", "INTVKL"),
    "East West Interconnector": ("ireland", "INTEW"),
    "Auchencrosh (interconnector CCT)": ("ireland", "INTIRL"),
    "Greenlink": ("ireland", "INTGRNL"),
}


def resources(dataset: str) -> dict[str, str]:
    payload = json.loads(_download(API.format(dataset)))["result"]["resources"]
    return {str(r.get("name", "")): str(r["path"]) for r in payload}


def fes_tables() -> None:
    out = ROOT / "data/fes"
    out.mkdir(parents=True, exist_ok=True)
    for dataset, files in TABLES.items():
        found = resources(dataset)
        for name, filename in files.items():
            (out / filename).write_bytes(_download(found[name]))
            print(f"{filename}: {found[name]}")


def interconnectors() -> None:
    url = next(iter(resources("interconnector-register").values()))
    rows = list(csv.DictReader(io.StringIO(_download(url).decode("utf-8-sig"))))
    built = [row for row in rows if row["Project Status"] == "Built"]
    # Moyle is listed in two stages; its total is the later stage's.
    latest: dict[str, dict[str, str]] = {}
    for row in built:
        if row["Project Name"] in LINKS:
            latest[row["Project Name"]] = row
    unknown = sorted(
        {r["Project Name"] for r in built} - set(LINKS) - {"Isle of Man Interconnector"}
    )
    if unknown:
        raise ValueError(f"built interconnectors without a neighbour: {', '.join(unknown)}")
    path = ROOT / "data/system/interconnectors.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["link", "neighbour", "bmrs_fuel_type", "import_mw", "export_mw", "connection_site"]
        )
        for name, row in latest.items():
            neighbour, fuel = LINKS[name]
            writer.writerow(
                [
                    name,
                    neighbour,
                    fuel,
                    row["MW Import - Total"],
                    row["MW Export - Total"],
                    row["Connection Site"],
                ]
            )
    print(f"interconnectors.csv: {len(latest)} links from {url}")


def main() -> None:
    fes_tables()
    interconnectors()


if __name__ == "__main__":
    main()
