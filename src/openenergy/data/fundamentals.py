"""What is known about tomorrow at a day-ahead decision: gas price, demand and wind forecasts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
import pandas as pd

from openenergy.errors import DataError

FUNDAMENTALS_ATTRIBUTION = (
    "Gas price: Office for National Statistics, System Average Price (SAP) of gas, daily, "
    "from National Gas Transmission (https://www.ons.gov.uk/economy/"
    "economicoutputandproductivity/output/datasets/systemaveragepricesapofgas), Open "
    "Government Licence v3.0. Demand forecast: NESO, Day Ahead Demand Forecast "
    "(https://www.neso.energy/data-portal/1-day-ahead-demand-forecast), NESO Open Data "
    "Licence v1.0. Supported by National Energy SO Open Data. Wind forecast: Elexon BMRS "
    "WINDFOR (https://bmrs.elexon.co.uk/), BMRS data licence; contains BMRS data © Elexon "
    "Limited copyright and database right 2026. OpenEnergy is not affiliated with or "
    "endorsed by any of these bodies."
)
GAS_FILE = "gas_sap_daily.csv"
DEMAND_FILE = "neso_demand_day_ahead.csv"
WIND_FILE = "elexon_wind_day_ahead.csv"
# The forecasts and the daily gas price start in January 2018; forecasts train from here.
FUNDAMENTALS_FROM = pd.Timestamp("2018-01-15", tz="UTC")
# Linear interpolation between demand cardinal points, which are up to a few hours apart.
_DEMAND_GAP = pd.Timedelta(hours=6)

FloatArray = npt.NDArray[np.float64]


class FundamentalsSource:
    """Reads the files written by ``scripts/fetch_fundamentals.py`` from one directory."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self._frames: dict[str, pd.DataFrame] = {}

    def gas_daily(self) -> pd.Series[float]:
        """System Average Price of gas by gas day (UTC midnight), GBP per MWh (gross CV)."""
        frame = self._read(GAS_FILE, ["date", "sap_p_per_kwh"])
        index = pd.DatetimeIndex(pd.to_datetime(frame["date"])).tz_localize("UTC")
        return pd.Series(frame["sap_p_per_kwh"].to_numpy(dtype=np.float64) * 10, index=index)

    def gas(self, index: pd.DatetimeIndex, lag_days: int = 0) -> FloatArray:
        """Each timestamp's gas price from ``lag_days`` before its UTC day; NaN where unknown."""
        days = index.normalize() - pd.Timedelta(days=lag_days)
        return np.asarray(self.gas_daily().reindex(days), dtype=np.float64)

    def demand(self, index: pd.DatetimeIndex, decision: pd.DatetimeIndex) -> FloatArray:
        """National demand forecast (MW) at each timestamp, as issued by its ``decision`` time.

        Points are interpolated linearly in time, never across more than six hours; NaN where
        no forecast had been issued.
        """
        out = np.full(len(index), np.nan)
        for when, rows in _groups(decision):
            targets = index[rows]
            points = self._known(
                "demand", DEMAND_FILE, when, targets[0] - _DEMAND_GAP, targets[-1] + _DEMAND_GAP
            )
            if len(points) >= 2:
                out[rows] = _interpolate(points, targets)
        return out

    def wind(self, index: pd.DatetimeIndex, decision: pd.DatetimeIndex) -> FloatArray:
        """Wind generation forecast (MW) as issued by each timestamp's ``decision`` time."""
        out = np.full(len(index), np.nan)
        for when, rows in _groups(decision):
            targets = index[rows]
            known = self._known("wind", WIND_FILE, when, targets[0], targets[-1])
            out[rows] = np.asarray(known.reindex(targets), dtype=np.float64)
        return out

    def _known(
        self, kind: str, name: str, decision: pd.Timestamp, first: pd.Timestamp, last: pd.Timestamp
    ) -> pd.Series[float]:
        """For targets from ``first`` to ``last``, the latest value issued by ``decision``."""
        frame = self._frames.get(name)
        if frame is None:
            raw = self._read(name, ["target_utc", f"{kind}_mw", "issued_utc"])
            frame = pd.DataFrame(
                {
                    "value": raw[f"{kind}_mw"].to_numpy(dtype=np.float64),
                    "issued": pd.DatetimeIndex(pd.to_datetime(raw["issued_utc"], utc=True)),
                },
                index=pd.DatetimeIndex(pd.to_datetime(raw["target_utc"], utc=True)),
            )
            frame = frame.sort_index(kind="stable")
            self._frames[name] = frame
        targets = pd.DatetimeIndex(frame.index)
        part = frame.iloc[targets.searchsorted(first) : targets.searchsorted(last, side="right")]
        part = part[part["issued"] <= decision].sort_values("issued", kind="stable")
        part = part[~part.index.duplicated(keep="last")].sort_index()
        return part["value"]

    def _read(self, name: str, columns: list[str]) -> pd.DataFrame:
        path = self.directory / name
        if not path.is_file():
            raise DataError(
                f"fundamentals file not found: {path} (run scripts/fetch_fundamentals.py)"
            )
        frame = pd.read_csv(path)
        missing = sorted(set(columns) - set(frame.columns))
        if missing:
            raise DataError(f"{name} is missing columns: {', '.join(missing)}")
        return frame


def decisions(index: pd.DatetimeIndex, lead_hours: float) -> pd.DatetimeIndex:
    """Each timestamp's decision time: its UTC day start minus ``lead_hours``."""
    return pd.DatetimeIndex(index.normalize() - pd.Timedelta(hours=lead_hours))


IntArray = npt.NDArray[np.intp]


def _groups(decision: pd.DatetimeIndex) -> list[tuple[pd.Timestamp, IntArray]]:
    """Row positions sharing each decision time, in order (rows are sorted in time)."""
    codes, uniques = pd.factorize(decision)
    order = np.argsort(codes, kind="stable").astype(np.intp)
    bounds = np.flatnonzero(np.diff(codes[order])) + 1
    return [
        (pd.Timestamp(uniques[codes[part[0]]]), part)
        for part in np.split(order, bounds)
        if part.size
    ]


def _nanoseconds(index: pd.DatetimeIndex) -> FloatArray:
    return index.tz_convert(None).as_unit("ns").to_numpy().astype(np.int64).astype(np.float64)


def _interpolate(points: pd.Series[float], targets: pd.DatetimeIndex) -> FloatArray:
    """Linear in time between known points; NaN outside them or across gaps over six hours."""
    x = _nanoseconds(pd.DatetimeIndex(points.index))
    y = points.to_numpy(dtype=np.float64)
    t = _nanoseconds(targets)
    values: FloatArray = np.interp(t, x, y, left=np.nan, right=np.nan)
    right = np.clip(np.searchsorted(x, t), 1, len(x) - 1)
    on_point = x[np.clip(np.searchsorted(x, t), 0, len(x) - 1)] == t
    gap = x[right] - x[right - 1]
    values[(gap > _DEMAND_GAP.value) & ~on_point] = np.nan
    return values
