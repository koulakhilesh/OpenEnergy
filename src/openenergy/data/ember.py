"""GB hourly day-ahead prices from Ember, converted to GBP with ECB reference rates."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from openenergy.data.opsd import OPSD_ATTRIBUTION, OPSDCsvSource
from openenergy.data.series import PriceSeries
from openenergy.errors import DataError

EMBER_ATTRIBUTION = (
    "GB day-ahead prices: Ember, European Wholesale Electricity Price Data (hourly, United "
    "Kingdom), https://ember-energy.org/data/european-wholesale-electricity-price-data/, "
    "licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); Ember's "
    "primary sources are ENTSO-E and EMR Settlement. Converted from EUR to GBP with European "
    "Central Bank euro reference rates (source: ECB), using the latest rate on or before each "
    "day. OpenEnergy is not affiliated with or endorsed by Ember or the ECB."
)
# OPSD names the GB zone GB_GBN; Ember's UK file is the same GB day-ahead price.
ZONES = frozenset({"GB", "GB_GBN"})
_PRICE = "price_eur_per_mwh"
_RATE = "gbp_per_eur"


class EmberPriceSource:
    """Reads ``gb_day_ahead_ember.csv`` and ``ecb_gbp_per_eur.csv`` written by the fetch script.

    ``rates`` defaults to ``ecb_gbp_per_eur.csv`` next to the price file.
    """

    def __init__(self, path: str | Path, rates: str | Path | None = None) -> None:
        self.path = Path(path)
        self.rates = (
            Path(rates) if rates is not None else self.path.with_name("ecb_gbp_per_eur.csv")
        )

    def zones(self) -> list[str]:
        return sorted(ZONES)

    def prices(
        self, zone: str = "GB_GBN", start: date | None = None, end: date | None = None
    ) -> PriceSeries:
        """Hourly GBP/MWh over whole UTC days, ``start`` and ``end`` inclusive."""
        if zone not in ZONES:
            raise DataError(f"Ember source covers GB only (GB or GB_GBN), got {zone!r}")
        eur = _read(self.path, "utc_timestamp", _PRICE)
        eur.index = pd.DatetimeIndex(pd.to_datetime(eur.index, utc=True, format="ISO8601"))
        series = PriceSeries(eur * self._rate(eur.index), currency="GBP", zone="GB_GBN")
        if start is None and end is None:
            return series
        return series.between(start, end)

    def _rate(self, index: pd.DatetimeIndex) -> pd.Series[float]:
        table = _read(self.rates, "date", _RATE)
        days = pd.DatetimeIndex(pd.to_datetime(table.index)).as_unit("ns")
        wanted = index.tz_convert(None).normalize().as_unit("ns")
        position = np.searchsorted(days.to_numpy(), wanted.to_numpy(), side="right") - 1
        if (position < 0).any():
            first = index[position < 0][0]
            raise DataError(f"no ECB rate on or before {first.date()} in {self.rates.name}")
        return pd.Series(table.to_numpy(dtype=float)[position], index=index)


def _read(path: Path, index: str, column: str) -> pd.Series[float]:
    if not path.is_file():
        raise DataError(f"file not found: {path}")
    frame = pd.read_csv(path)
    missing = sorted({index, column} - set(frame.columns))
    if missing:
        raise DataError(f"{path.name} is missing columns: {', '.join(missing)}")
    return pd.Series(frame[column].to_numpy(dtype=float), index=frame[index], name=column)


def gb_prices(paths: Sequence[str | Path], start: date, end: date) -> tuple[PriceSeries, list[str]]:
    """GB hourly day-ahead prices from OPSD and/or Ember files, earlier files taking priority.

    Each file's type is read from its header. A later file only adds hours outside the span
    already covered, never filling gaps inside it (Ember interpolates its own gaps). Returns
    the prices and the attribution of every file that supplied at least one value.
    """
    combined: pd.Series[float] | None = None
    attribution: list[str] = []
    for path in map(Path, paths):
        if not path.is_file():
            raise DataError(f"price file not found: {path}")
        ember = _PRICE in pd.read_csv(path, nrows=0).columns
        source = EmberPriceSource(path) if ember else OPSDCsvSource(path)
        try:
            values = source.prices("GB_GBN", start, end).prices
        except DataError as exc:
            if "no data between" in str(exc):
                continue
            raise
        if combined is not None:
            inside = (values.index >= combined.index[0]) & (values.index <= combined.index[-1])
            values = values[~inside]
        if values.dropna().empty:
            continue
        combined = values if combined is None else pd.concat([combined, values]).sort_index()
        attribution.append(EMBER_ATTRIBUTION if ember else OPSD_ATTRIBUTION)
    if combined is None:
        raise DataError(f"no GB prices between {start} and {end} in {', '.join(map(str, paths))}")
    grid = pd.date_range(combined.index[0], combined.index[-1], freq="1h")
    return PriceSeries(combined.reindex(grid), currency="GBP", zone="GB_GBN"), attribution
