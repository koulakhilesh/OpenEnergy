"""GB carbon intensity from NESO's Carbon Intensity API extract."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from openenergy.data.series import _between, _validate
from openenergy.errors import DataError

CARBON_ATTRIBUTION = (
    "Carbon intensity data: National Energy System Operator (NESO), Carbon Intensity API, "
    "https://carbonintensity.org.uk/, licensed under CC BY 4.0 "
    "(https://creativecommons.org/licenses/by/4.0/). Changes: values outside "
    "0-1000 gCO2/kWh treated as missing; half-hours averaged to the analysis step. "
    "OpenEnergy is not affiliated with or endorsed by NESO."
)
KINDS = ("actual", "forecast")
# No GB fuel exceeds this (coal is about 937 gCO2/kWh); larger values are archive errors.
MAX_INTENSITY = 1000.0
_HOUR = pd.Timedelta(hours=1)


@dataclass(frozen=True, eq=False)
class IntensitySeries:
    """Average grid carbon intensity in gCO2/kWh (= kg/MWh).

    ``rejected`` counts values outside [0, 1000] that were treated as missing.
    """

    values: pd.Series[float] = field(repr=False)
    kind: str
    rejected: int = 0
    step: pd.Timedelta = field(init=False)

    def __post_init__(self) -> None:
        values, step = _validate(self.values)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "step", step)

    @property
    def step_hours(self) -> float:
        return float(self.step / _HOUR)


class CarbonIntensitySource:
    """Reads ``utc_timestamp, forecast, actual`` half-hourly CSVs written by the fetch script."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def intensity(
        self,
        kind: str = "actual",
        start: date | None = None,
        end: date | None = None,
        step: pd.Timedelta | None = None,
    ) -> IntensitySeries:
        """Intensity over whole UTC days, optionally averaged to a coarser ``step``.

        An averaged interval is missing unless every half-hour in it is present.
        """
        if kind not in KINDS:
            raise DataError(f"kind must be one of {', '.join(KINDS)}, got {kind!r}")
        if not self.path.is_file():
            raise DataError(f"carbon intensity file not found: {self.path}")
        frame = pd.read_csv(self.path, usecols=["utc_timestamp", kind])
        index = pd.DatetimeIndex(pd.to_datetime(frame["utc_timestamp"], utc=True, format="ISO8601"))
        raw = pd.Series(frame[kind].to_numpy(dtype=float), index=index)
        if start is not None or end is not None:
            raw = _between(raw, start, end, "GB")
        impossible = (raw < 0) | (raw > MAX_INTENSITY)
        values = raw.mask(impossible)
        series = IntensitySeries(values, kind, rejected=int(impossible.sum()))
        if step is None or step == series.step:
            return series
        return _average(series, step)


def _average(series: IntensitySeries, step: pd.Timedelta) -> IntensitySeries:
    if step < series.step or step % series.step != pd.Timedelta(0):
        raise DataError(f"step {step} must be a multiple of the data step {series.step}")
    per_step = int(step / series.step)
    grouped = series.values.resample(step)
    averaged = grouped.mean().where(grouped.count() == per_step)
    return dataclasses.replace(series, values=averaged)
