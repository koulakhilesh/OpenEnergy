"""What GB's grid batteries actually did: the files written by ``scripts/fetch_fleet.py``."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from openenergy.errors import DataError

REAL_BATTERIES_ATTRIBUTION = (
    "Real batteries: Elexon BMRS Insights API (https://bmrs.elexon.co.uk/): BM unit register, "
    "physical notifications (PN), metered output per BM unit (B1610) and indicative Balancing "
    "Mechanism volumes and cashflows, BMRS data licence; contains BMRS data © Elexon Limited "
    "copyright and database right 2026. Changes: battery units chosen by name, values summed "
    "by unit and UTC day. OpenEnergy is not affiliated with or endorsed by Elexon."
)
UNITS_FILE = "battery_units.csv"
DAILY_FILE = "battery_daily.csv"
HOURLY_FILE = "fleet_hourly.csv"
DAILY_COLUMNS = (
    "pn_mwh_out",
    "pn_mwh_in",
    "pn_value_day_ahead_gbp",
    "metered_mwh_out",
    "metered_mwh_in",
    "metered_value_day_ahead_gbp",
    "bm_offer_mwh",
    "bm_bid_mwh",
    "bm_offer_gbp",
    "bm_bid_gbp",
    "imbalance_mwh",
    "imbalance_gbp",
)


class RealBatteries:
    """GB battery BM units: the register, daily totals per unit and the fleet each hour."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def _read(self, name: str, columns: tuple[str, ...]) -> pd.DataFrame:
        path = self.directory / name
        if not path.is_file():
            raise DataError(f"real battery file not found: {path}")
        frame = pd.read_csv(path)
        missing = sorted(set(columns) - set(frame.columns))
        if missing:
            raise DataError(f"{name} is missing columns: {', '.join(missing)}")
        return frame

    def units(self) -> pd.DataFrame:
        """One row per battery BM unit, indexed by its Elexon BM unit id."""
        frame = self._read(UNITS_FILE, ("unit", "name", "generation_capacity_mw", "gsp_group"))
        return frame.set_index("unit")

    def daily(self) -> pd.DataFrame:
        """Daily totals per unit (MWh and GBP), indexed by UTC date and unit; missing as NaN."""
        frame = self._read(DAILY_FILE, ("date", "unit", *DAILY_COLUMNS))
        frame["date"] = pd.to_datetime(frame["date"])
        return frame.set_index(["date", "unit"]).sort_index()

    def hourly(self) -> pd.DataFrame:
        """The whole battery fleet each UTC hour: net, export and import MW and units running."""
        frame = self._read(HOURLY_FILE, ("utc_timestamp", "metered_net_mw", "pn_net_mw", "units"))
        index = pd.DatetimeIndex(pd.to_datetime(frame["utc_timestamp"], utc=True, format="ISO8601"))
        return frame.drop(columns="utc_timestamp").set_index(index)

    def by_year(self, by_zone: bool = False) -> pd.DataFrame:
        """Fleet totals by year (and zone), and per MW of registered capacity for the days each
        unit ran.

        ``mw_years`` adds each unit's registered generation capacity over the days it had a
        PN or metered output, so per-MW figures compare with a 1 MW battery for a year.
        """
        daily = self.daily()
        units = self.units()
        # Registered generation capacity, or the fetch script's fallback where that is zero.
        capacity = (
            units["capacity_mw"] if "capacity_mw" in units else units["generation_capacity_mw"]
        )
        frame = daily.reset_index()
        frame["year"] = frame["date"].dt.year
        frame["mw"] = frame["unit"].map(capacity).astype(float)
        if frame["mw"].isna().any():
            unknown = sorted(frame.loc[frame["mw"].isna(), "unit"].unique())
            raise DataError(f"units missing from {UNITS_FILE}: {', '.join(unknown)}")
        keys = ["year"]
        if by_zone:
            if "zone" not in units:
                raise DataError(f"{UNITS_FILE} has no zone column; rerun scripts/fetch_fleet.py")
            frame["zone"] = frame["unit"].map(units["zone"].fillna("")).replace("", "unknown")
            keys.append("zone")
        frame["bm_net_gbp"] = frame["bm_offer_gbp"].fillna(0) + frame["bm_bid_gbp"].fillna(0)
        # Settlement: the contracted position (PN, priced here at day-ahead), BM actions, and
        # what the meter shows beyond both at the system price. Only the contract price is assumed.
        frame["estimated_total_gbp"] = (
            frame["pn_value_day_ahead_gbp"].fillna(0)
            + frame["bm_net_gbp"]
            + frame["imbalance_gbp"].fillna(0)
        )
        values = [
            "pn_value_day_ahead_gbp",
            "metered_value_day_ahead_gbp",
            "bm_net_gbp",
            "imbalance_gbp",
            "estimated_total_gbp",
        ]
        grouped = frame.groupby(keys)
        sums = grouped[["metered_mwh_out", "metered_mwh_in", *values]].sum()
        sums["units"] = grouped["unit"].nunique()
        sums["mw_years"] = grouped["mw"].sum() / 365.0
        # Hours a year at full power: energy discharged per MW (duration is not registered).
        sums["discharge_hours"] = sums["metered_mwh_out"] / sums["mw_years"]
        for name in values:
            sums[name.removesuffix("_gbp") + "_per_mw_year"] = sums[name] / sums["mw_years"]
        sums["round_trip"] = sums["metered_mwh_out"] / sums["metered_mwh_in"].replace(0, np.nan)
        return sums
