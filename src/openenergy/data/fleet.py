"""GB fleet capacity, efficiency, fuel prices and carbon prices for the system model."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from openenergy.errors import DataError

FLEET_ATTRIBUTION = (
    "Fleet and fuel data: Department for Energy Security and Net Zero, Digest of UK Energy "
    "Statistics 2026, tables 5.8 and 5.10 (https://www.gov.uk/government/statistics/"
    "electricity-chapter-5-digest-of-united-kingdom-energy-statistics-dukes), and Quarterly "
    "Energy Prices table 3.2.1 (https://www.gov.uk/government/statistical-data-sets/"
    "prices-of-fuels-purchased-by-major-power-producers); HM Revenue & Customs, Excise "
    "Notice CCL1/6 carbon price support rates. Contains public sector information licensed "
    "under the Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/"
    "open-government-licence/version/3/). EU ETS prices: World Bank, Carbon Pricing "
    "Dashboard (https://carbonpricingdashboard.worldbank.org/, accessed 2026-10-10), "
    "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Exchange rates: source "
    "European Central Bank; OpenEnergy derives a USD-to-GBP cross rate from its EUR "
    "reference rates. Changes: GB totals from England and Wales plus Scotland; capacity "
    "interpolated between year ends; units converted to GBP per MWh. OpenEnergy is not "
    "affiliated with or endorsed by any of these bodies."
)
CAPACITY_COLUMNS = (
    "ccgt_mw", "coal_mw", "gas_turbine_mw", "oil_engine_mw", "nuclear_mw", "pumped_storage_mw",
)  # fmt: skip
FUEL_COLUMNS = {"gas": "gas_p_per_kwh", "coal": "coal_p_per_kwh", "oil": "oil_p_per_kwh"}
# The carbon price support rates from April 2016 are set at GBP 18/tCO2, so rate / 18 gives
# HMRC's emission factor per MWh of fuel (gross calorific value).
CPS_BASIS_GBP_PER_T = 18.0
EMISSION_FACTORS = {
    "gas": 0.00331 * 1000 / CPS_BASIS_GBP_PER_T,
    "coal": 1.5479 * 3.6 / CPS_BASIS_GBP_PER_T,
}
_GJ_PER_MWH = 3.6


class SystemInputs:
    """Reads ``fleet.csv``, ``fuel_prices.csv`` and ``carbon_prices.csv`` from one directory."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def capacity(self, index: pd.DatetimeIndex) -> pd.DataFrame:
        """MW at each timestamp, linear in time between end-of-year values."""
        fleet = self._read("fleet.csv", ["year", *CAPACITY_COLUMNS]).set_index("year")
        ends = pd.DatetimeIndex(
            [pd.Timestamp(year + 1, 1, 1, tz="UTC") for year in fleet.index.astype(int)]
        )
        _check_within(index, ends[0], ends[-1], "fleet.csv")
        positions = _nanoseconds(index).astype(np.float64)
        knots = _nanoseconds(ends).astype(np.float64)
        columns = {
            name: np.interp(positions, knots, fleet[name].to_numpy(dtype=np.float64))
            for name in CAPACITY_COLUMNS
        }
        return pd.DataFrame(columns, index=index)

    def efficiency(self, year: int) -> dict[str, float]:
        """Fleet-average thermal efficiency (gross calorific value) for ``year``."""
        fleet = self._read("fleet.csv", ["year", "ccgt_efficiency", "coal_efficiency"])
        row = fleet[fleet["year"] == year]
        if row.empty:
            raise DataError(f"no efficiency for {year} in fleet.csv")
        return {
            "ccgt": float(row["ccgt_efficiency"].iloc[0]),
            "coal": float(row["coal_efficiency"].iloc[0]),
        }

    def fuel_prices(self, index: pd.DatetimeIndex) -> pd.DataFrame:
        """GBP per MWh of fuel at each timestamp, from the quarter it falls in."""
        prices = self._read("fuel_prices.csv", ["year", "quarter", *FUEL_COLUMNS.values()])
        keys = pd.MultiIndex.from_arrays([index.year, index.quarter])
        table = prices.set_index(["year", "quarter"])
        found = keys.isin(table.index)
        if not found.all():
            first = index[~found][0]
            raise DataError(f"no fuel prices for {first.year} Q{first.quarter}")
        rows = table.loc[keys]
        return pd.DataFrame(
            {
                fuel: rows[column].to_numpy(dtype=np.float64) * 10
                for fuel, column in FUEL_COLUMNS.items()
            },
            index=index,
        )

    def carbon_prices(self, index: pd.DatetimeIndex) -> pd.DataFrame:
        """EU ETS price (GBP/t) and carbon price support (GBP/MWh of fuel) at each timestamp.

        Each row applies from its ``valid_from`` date (1 April) to the next.
        """
        table = self._read(
            "carbon_prices.csv",
            [
                "valid_from", "eu_ets_usd_per_t", "usd_per_eur", "gbp_per_eur",
                "cps_gas_gbp_per_kwh", "cps_coal_gbp_per_gj",
            ],
        )  # fmt: skip
        starts = pd.DatetimeIndex(pd.to_datetime(table["valid_from"], utc=True))
        _check_within(index, starts[0], None, "carbon_prices.csv")
        row = np.searchsorted(_nanoseconds(starts), _nanoseconds(index), side="right") - 1
        rows = table.iloc[row]
        eu_ets = rows["eu_ets_usd_per_t"] / rows["usd_per_eur"] * rows["gbp_per_eur"]
        return pd.DataFrame(
            {
                "eu_ets_gbp_per_t": eu_ets.to_numpy(dtype=np.float64),
                "cps_gas": rows["cps_gas_gbp_per_kwh"].to_numpy(dtype=np.float64) * 1000,
                "cps_coal": rows["cps_coal_gbp_per_gj"].to_numpy(dtype=np.float64) * _GJ_PER_MWH,
            },
            index=index,
        )

    def _read(self, name: str, columns: list[str]) -> pd.DataFrame:
        path = self.directory / name
        if not path.is_file():
            raise DataError(f"system data file not found: {path}")
        frame = pd.read_csv(path)
        missing = sorted(set(columns) - set(frame.columns))
        if missing:
            raise DataError(f"{name} is missing columns: {', '.join(missing)}")
        return frame


def _nanoseconds(index: pd.DatetimeIndex) -> np.ndarray[tuple[int], np.dtype[np.int64]]:
    return index.tz_convert(None).as_unit("ns").to_numpy().astype(np.int64)


def _check_within(
    index: pd.DatetimeIndex, first: pd.Timestamp, last: pd.Timestamp | None, name: str
) -> None:
    if index.empty:
        raise DataError("index is empty")
    if index.tz is None or str(index.tz) != "UTC":
        raise DataError(f"index must be tz-aware UTC, got {index.tz}")
    if index.min() < first or (last is not None and index.max() > last):
        bound = f"{first}" if last is None else f"{first} to {last}"
        raise DataError(f"{name} covers {bound}; requested {index.min()} to {index.max()}")
