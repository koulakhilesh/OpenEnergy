"""Open Power System Data (OPSD) time-series CSV source."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from openenergy.data.series import PriceSeries, ProfileSeries, _between, _validate
from openenergy.errors import DataError

OPSD_ATTRIBUTION = (
    "Open Power System Data. 2020. Data Package Time series. Version 2020-10-06. "
    "https://doi.org/10.25832/time_series/2020-10-06. "
    "(Primary data from various sources, for a complete list see URL)."
)

_TIMESTAMP = "utc_timestamp"
_PRICE_SUFFIX = "_price_day_ahead"
_PROFILE_SUFFIX = "_profile"
# OPSD publishes GB day-ahead prices in GBP and every other zone in EUR.
_GBP_ZONES = frozenset({"GB_GBN"})


class OPSDCsvSource:
    """Reads day-ahead prices and capacity-factor profiles from an OPSD singleindex CSV."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def zones(self) -> list[str]:
        """Bidding zones with a day-ahead price column."""
        return sorted(
            column.removesuffix(_PRICE_SUFFIX)
            for column in self._columns()
            if column.endswith(_PRICE_SUFFIX)
        )

    def technologies(self, zone: str) -> list[str]:
        """Technologies with a capacity-factor profile for ``zone``."""
        prefix = f"{zone}_"
        return sorted(
            column.removeprefix(prefix).removesuffix(_PROFILE_SUFFIX)
            for column in self._columns()
            if column.startswith(prefix) and column.endswith(_PROFILE_SUFFIX)
        )

    def prices(self, zone: str, start: date | None = None, end: date | None = None) -> PriceSeries:
        """Day-ahead prices for ``zone`` over whole UTC days, ``start`` and ``end`` inclusive."""
        column = f"{zone}{_PRICE_SUFFIX}"
        if column not in self._columns():
            available = ", ".join(self.zones()) or "none"
            raise DataError(f"zone {zone!r} not in {self.path.name}; available: {available}")
        currency = "GBP" if zone in _GBP_ZONES else "EUR"
        series = PriceSeries(self._load(column), currency=currency, zone=zone)
        if start is None and end is None:
            return series
        return series.between(start, end)

    def profile(
        self, zone: str, technology: str, start: date | None = None, end: date | None = None
    ) -> ProfileSeries:
        """Capacity factors for ``technology`` in ``zone``, capped to [0, 1]."""
        column = f"{zone}_{technology}{_PROFILE_SUFFIX}"
        if column not in self._columns():
            available = ", ".join(self.technologies(zone)) or "none"
            raise DataError(
                f"no {technology!r} profile for {zone} in {self.path.name}; available: {available}"
            )
        values = self._load(column)
        if start is not None or end is not None:
            values = _between(values, start, end, zone)
        # Reported capacity can lag new build, pushing generation / capacity above 1.
        clipped = int(((values > 1) | (values < 0)).sum())
        return ProfileSeries(values.clip(0.0, 1.0), technology, zone, clipped=clipped)

    def series(
        self, column: str, start: date | None = None, end: date | None = None
    ) -> pd.Series[float]:
        """Any column as a validated series over whole UTC days, ``start`` and ``end`` inclusive."""
        if column not in self._columns():
            prefix = column.split("_", 2)[:2]
            similar = [c for c in self._columns() if c.split("_", 2)[:2] == prefix]
            hint = f"; similar: {', '.join(similar)}" if similar else ""
            raise DataError(f"no column {column!r} in {self.path.name}{hint}")
        values, _ = _validate(self._load(column))
        return values if start is None and end is None else _between(values, start, end, column)

    def load(
        self, zone: str, start: date | None = None, end: date | None = None
    ) -> pd.Series[float]:
        """Actual load in MW (ENTSO-E Transparency)."""
        return self.series(f"{zone}_load_actual_entsoe_transparency", start, end).rename("load_mw")

    def generation(
        self, zone: str, technology: str, start: date | None = None, end: date | None = None
    ) -> pd.Series[float]:
        """Actual generation in MW for ``technology`` (e.g. ``solar``, ``wind``)."""
        column = f"{zone}_{technology}_generation_actual"
        return self.series(column, start, end).rename(f"{technology}_mw")

    def _load(self, column: str) -> pd.Series[float]:
        if _TIMESTAMP not in self._columns():
            raise DataError(f"{self.path} has no {_TIMESTAMP!r} column")
        frame = pd.read_csv(self.path, usecols=[_TIMESTAMP, column])
        try:
            index = pd.DatetimeIndex(pd.to_datetime(frame[_TIMESTAMP], utc=True, format="ISO8601"))
        except ValueError as exc:
            raise DataError(f"cannot parse {_TIMESTAMP} in {self.path}: {exc}") from exc
        return pd.Series(frame[column].to_numpy(dtype=float), index=index, name=column)

    def _columns(self) -> list[str]:
        if not self.path.is_file():
            raise DataError(f"OPSD file not found: {self.path}")
        return list(pd.read_csv(self.path, nrows=0).columns)
