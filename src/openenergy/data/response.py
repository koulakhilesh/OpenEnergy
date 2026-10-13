"""GB dynamic frequency response (DC, DM, DR): auction clearing prices and utilisation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
import pandas as pd

from openenergy.errors import DataError

RESPONSE_ATTRIBUTION = (
    "Frequency response: National Energy System Operator (NESO), Dynamic Containment, "
    "Regulation and Moderation auction results "
    "(https://www.neso.energy/data-portal/dynamic-containment-data) and Enduring Auction "
    "Capability (EAC) auction results (https://www.neso.energy/data-portal/eac-auction-results); "
    "utilisation derived from System frequency data "
    "(https://www.neso.energy/data-portal/system-frequency-data); accessed 2026-10-13, NESO "
    "Open Data Licence v1.0 (https://www.neso.energy/data-portal/neso-open-licence). Supported "
    "by National Energy SO Open Data. Changes: response clearing prices and volumes per block "
    "kept; one-second frequency reduced to monthly average delivery per MW. OpenEnergy is not "
    "affiliated with or endorsed by NESO."
)
FloatArray = npt.NDArray[np.float64]
Direction = Literal["low", "high"]
NOMINAL_HZ = 50.0
DEADBAND_HZ = 0.015


@dataclass(frozen=True)
class Service:
    """A response product: ``low`` exports when frequency falls, ``high`` imports when it rises.

    ``envelope`` lists (deviation beyond 50 Hz, fraction of contracted MW) points after the
    deadband, from NESO's Response Services Service Terms; delivery is linear between them.
    """

    name: str
    direction: Direction
    duration_hours: float
    envelope: tuple[tuple[float, float], ...]

    def delivered(self, frequency_hz: FloatArray) -> FloatArray:
        """Fraction of the contracted MW delivered at each frequency sample."""
        deviation = (
            NOMINAL_HZ - frequency_hz if self.direction == "low" else frequency_hz - NOMINAL_HZ
        )
        x = [0.0, DEADBAND_HZ, *(hz for hz, _ in self.envelope)]
        y = [0.0, 0.0, *(fraction for _, fraction in self.envelope)]
        return np.interp(np.clip(deviation, 0.0, None), x, y)


_DC = ((0.2, 0.05), (0.5, 1.0))
_DM = ((0.1, 0.05), (0.2, 1.0))
_DR = ((0.2, 1.0),)
SERVICES: dict[str, Service] = {
    "DCL": Service("DCL", "low", 0.25, _DC),
    "DCH": Service("DCH", "high", 0.25, _DC),
    "DML": Service("DML", "low", 0.5, _DM),
    "DMH": Service("DMH", "high", 0.5, _DM),
    "DRL": Service("DRL", "low", 1.0, _DR),
    "DRH": Service("DRH", "high", 1.0, _DR),
}
PRICES_FILE = "gb_dynamic_response.csv"
UTILISATION_FILE = "gb_response_utilisation.csv"


def utilisation(frequency_hz: FloatArray) -> dict[str, float]:
    """Average delivery per contracted MW (= MWh per MW per hour) over the samples."""
    valid = frequency_hz[np.isfinite(frequency_hz)]
    if valid.size == 0:
        raise DataError("no valid frequency samples")
    return {name: float(service.delivered(valid).mean()) for name, service in SERVICES.items()}


@dataclass(frozen=True, eq=False)
class ResponseMarket:
    """Clearing prices (GBP/MW/h) per delivery block and monthly utilisation per service.

    ``prices`` is indexed by block start (UTC) with an ``end`` column and one column per
    service; ``utilisation`` is indexed by month start (UTC).
    """

    prices: pd.DataFrame = field(repr=False)
    utilisation: pd.DataFrame = field(repr=False)

    @property
    def services(self) -> list[str]:
        return [column for column in self.prices.columns if column != "end"]

    def utilisation_at(self, starts: pd.DatetimeIndex) -> pd.DataFrame:
        """Each block's monthly factors; months without frequency data use the overall mean."""
        months = starts.tz_convert("UTC").tz_localize(None).to_period("M").to_timestamp()
        factors = self.utilisation.reindex(months.tz_localize("UTC"))
        factors = factors.fillna(self.utilisation.mean())
        factors.index = starts
        return factors


class ResponseSource:
    """Reads the block prices and monthly utilisation CSVs written by the fetch script."""

    def __init__(self, path: str | Path, utilisation_path: str | Path | None = None) -> None:
        self.path = Path(path)
        self.utilisation_path = (
            self.path.with_name(UTILISATION_FILE)
            if utilisation_path is None
            else Path(utilisation_path)
        )

    def market(self, services: list[str]) -> ResponseMarket:
        unknown = sorted(set(services) - set(SERVICES))
        if unknown:
            raise DataError(f"unknown response services: {', '.join(unknown)}")
        if not services:
            raise DataError("at least one response service is required")
        for path in (self.path, self.utilisation_path):
            if not path.is_file():
                raise DataError(f"response file not found: {path}")
        frame = pd.read_csv(self.path)
        columns = {f"{name.lower()}_gbp_per_mw_h": name for name in services}
        missing = sorted(set(columns) - set(frame.columns))
        if missing:
            raise DataError(f"{self.path.name} lacks columns: {', '.join(missing)}")
        start = pd.DatetimeIndex(pd.to_datetime(frame["utc_start"], utc=True, format="ISO8601"))
        prices = frame[list(columns)].rename(columns=columns).set_index(start)
        prices.insert(
            0, "end", pd.DatetimeIndex(pd.to_datetime(frame["utc_end"], utc=True, format="ISO8601"))
        )
        prices = prices.sort_index()
        ends = pd.DatetimeIndex(prices["end"])
        if not prices.index.is_unique:
            raise DataError(f"{self.path.name} has duplicate block starts")
        if (ends <= prices.index).any():
            raise DataError(f"{self.path.name} has blocks that end before they start")
        if (ends[:-1] > prices.index[1:]).any():
            raise DataError(f"{self.path.name} has overlapping blocks")

        usage = pd.read_csv(self.utilisation_path)
        factors = {name.lower(): name for name in services}
        missing = sorted(set(factors) - set(usage.columns))
        if missing:
            raise DataError(f"{self.utilisation_path.name} lacks columns: {', '.join(missing)}")
        months = pd.DatetimeIndex(pd.to_datetime(usage["month"], utc=True, format="ISO8601"))
        table = usage[list(factors)].rename(columns=factors).set_index(months).sort_index()
        if table.empty or table.isna().any().any() or ((table < 0) | (table > 1)).any().any():
            raise DataError(f"{self.utilisation_path.name} needs factors in [0, 1] for each month")
        return ResponseMarket(prices, table)
