"""NESO Future Energy Scenarios: capacity, storage and demand by pathway and year."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from openenergy.errors import DataError

FES_ATTRIBUTION = (
    "Future Energy Scenarios: National Energy System Operator (NESO), FES: Pathways to Net "
    "Zero 2025 and Ten Year Outlook 2026, Electricity Supply Data Table (ES1) and Electricity "
    "Demand Summary (ED1), https://www.neso.energy/data-portal/"
    "future-energy-scenario-electricity-supply-data-table-es1 and "
    "https://www.neso.energy/data-portal/fes-electricity-demand-summary-data-table-ed1 "
    "(accessed 2026-10-13), NESO Open Data Licence v1.0 "
    "(https://www.neso.energy/data-portal/neso-open-licence). Supported by National Energy "
    "SO Open Data. OpenEnergy is not affiliated with or endorsed by NESO."
)
# Pathway (or scenario) name -> file prefix of the edition that publishes it.
PATHWAYS = {
    "Holistic Transition": "fes2025",
    "Electric Engagement": "fes2025",
    "Hydrogen Evolution": "fes2025",
    "Falling Behind": "fes2025",
    "Ten Year Forecast": "fes2025",
    "Ten Year Outlook": "tyo2026",
}
_DEMAND_ITEMS = ("GBFES System Demand: Total", "Total System Demand")


class FesSource:
    """Reads the ES1 and ED1 tables written by ``scripts/fetch_fes.py`` (unchanged)."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def capacity_mw(self, pathway: str, year: int) -> pd.Series[float]:
        """Installed capacity (MW) by FES technology type, all connections summed."""
        return self.supply(pathway, year, "Capacity (MW)")

    def storage_gwh(self, pathway: str, year: int) -> pd.Series[float]:
        """Storage energy capacity (GWh) by FES technology type."""
        return self.supply(pathway, year, "Storage Capacity (GWh)")

    def demand_gwh(self, pathway: str, year: int) -> float:
        """Annual GB system demand (GWh, fiscal year)."""
        table = self._table(pathway, "ed1")
        rows = table[table["Data item"].isin(_DEMAND_ITEMS)]
        value = _column(rows, year, "ED1").dropna()
        if value.empty:
            raise DataError(f"FES ED1 has no system demand for {pathway} in {year}")
        return float(value.iloc[0])

    def years(self, pathway: str) -> list[int]:
        """Years with capacity data for the pathway."""
        table = self._table(pathway, "es1")
        capacity = table[table["Variable"] == "Capacity (MW)"]
        return [int(c) for c in table.columns if c.isdigit() and capacity[c].notna().any()]

    def supply(self, pathway: str, year: int, variable: str) -> pd.Series[float]:
        """Any ES1 variable (e.g. ``Export (TWh)``) summed by technology type."""
        table = self._table(pathway, "es1")
        rows = table[table["Variable"] == variable]
        values = _column(rows, year, "ES1")
        return values.fillna(0.0).groupby(rows["Type"]).sum()

    def _table(self, pathway: str, kind: str) -> pd.DataFrame:
        prefix = PATHWAYS.get(pathway)
        if prefix is None:
            raise DataError(f"unknown FES pathway {pathway!r}; choose from {', '.join(PATHWAYS)}")
        path = self.directory / f"{prefix}_{kind}.csv"
        if not path.is_file():
            raise DataError(f"FES table not found: {path}")
        table = pd.read_csv(path)
        name = "Pathway" if "Pathway" in table.columns else "Scenario"
        return table[table[name] == pathway]


def _column(rows: pd.DataFrame, year: int, table: str) -> pd.Series[float]:
    column = str(year)
    if column not in rows.columns:
        raise DataError(f"FES {table} has no {year} column")
    return pd.to_numeric(rows[column], errors="coerce")
