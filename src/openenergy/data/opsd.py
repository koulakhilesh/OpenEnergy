"""Open Power System Data (OPSD) time-series CSV source."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from openenergy.data.series import PriceSeries
from openenergy.errors import DataError

OPSD_ATTRIBUTION = (
    "Open Power System Data. 2020. Data Package Time series. Version 2020-10-06. "
    "https://doi.org/10.25832/time_series/2020-10-06. "
    "(Primary data from various sources, for a complete list see URL)."
)

_TIMESTAMP = "utc_timestamp"
_PRICE_SUFFIX = "_price_day_ahead"
# OPSD publishes GB day-ahead prices in GBP and every other zone in EUR.
_GBP_ZONES = frozenset({"GB_GBN"})


class OPSDCsvSource:
    """Reads day-ahead prices from an OPSD ``time_series_*_singleindex`` CSV."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def zones(self) -> list[str]:
        """Bidding zones with a day-ahead price column."""
        return sorted(
            column.removesuffix(_PRICE_SUFFIX)
            for column in self._columns()
            if column.endswith(_PRICE_SUFFIX)
        )

    def prices(self, zone: str, start: date | None = None, end: date | None = None) -> PriceSeries:
        """Day-ahead prices for ``zone`` over whole UTC days, ``start`` and ``end`` inclusive."""
        columns = self._columns()
        if _TIMESTAMP not in columns:
            raise DataError(f"{self.path} has no {_TIMESTAMP!r} column")
        column = f"{zone}{_PRICE_SUFFIX}"
        if column not in columns:
            available = ", ".join(self.zones()) or "none"
            raise DataError(f"zone {zone!r} not in {self.path.name}; available: {available}")

        frame = pd.read_csv(self.path, usecols=[_TIMESTAMP, column])
        try:
            index = pd.DatetimeIndex(pd.to_datetime(frame[_TIMESTAMP], utc=True, format="ISO8601"))
        except ValueError as exc:
            raise DataError(f"cannot parse {_TIMESTAMP} in {self.path}: {exc}") from exc

        values = pd.Series(frame[column].to_numpy(dtype=float), index=index, name=column)
        currency = "GBP" if zone in _GBP_ZONES else "EUR"
        series = PriceSeries(values, currency=currency, zone=zone)
        if start is None and end is None:
            return series
        return series.between(start, end)

    def _columns(self) -> list[str]:
        if not self.path.is_file():
            raise DataError(f"OPSD file not found: {self.path}")
        return list(pd.read_csv(self.path, nrows=0).columns)
