"""Renewable plants driven by capacity-factor profiles."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from openenergy.data.series import ProfileSeries
from openenergy.errors import ConfigError, DataError

_YEAR = pd.Timedelta(days=365)


@dataclass(frozen=True)
class RenewableSpec:
    """A plant of ``capacity_mw`` whose output declines by ``degradation_per_year``."""

    technology: str
    capacity_mw: float
    degradation_per_year: float = 0.0

    def __post_init__(self) -> None:
        if not self.technology:
            raise ConfigError("technology must be set, e.g. 'solar' or 'wind'")
        if not (math.isfinite(self.capacity_mw) and self.capacity_mw > 0):
            raise ConfigError(f"capacity_mw must be positive and finite, got {self.capacity_mw}")
        if not 0 <= self.degradation_per_year < 1:
            raise ConfigError(
                f"degradation_per_year must be in [0, 1), got {self.degradation_per_year}"
            )

    def generation_mw(
        self, profile: ProfileSeries, start_age_years: float = 0.0
    ) -> pd.Series[float]:
        """Available output in MW: capacity x capacity factor x (1 - degradation)^age.

        Age is ``start_age_years`` at the first interval of ``profile`` and grows with time.
        """
        if profile.technology != self.technology:
            raise DataError(f"{self.technology} plant given a {profile.technology} profile")
        if start_age_years < 0:
            raise ConfigError(f"start_age_years must be non-negative, got {start_age_years}")
        index = pd.DatetimeIndex(profile.values.index)
        age = start_age_years + np.asarray((index - index[0]) / _YEAR, dtype=np.float64)
        factor = (1.0 - self.degradation_per_year) ** age
        return pd.Series(
            self.capacity_mw * profile.values.to_numpy() * factor,
            index=index,
            name="generation_mw",
        )
