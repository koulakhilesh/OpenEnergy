"""Transparent filters for telemetry glitches in metered time series."""

from __future__ import annotations

import pandas as pd


def flag_glitches(
    values: pd.Series[float],
    spike_fraction: float = 0.25,
    dropout_fraction: float = 0.5,
) -> pd.Series[bool]:
    """Flag isolated spikes and dropouts in a smooth series such as demand.

    A spike deviates from its centred 5-interval median by more than ``spike_fraction``
    of the series' 99th percentile; a dropout falls below ``dropout_fraction`` of its
    centred 7-day median. Genuine ramps sit on their rolling median, so are not flagged.
    """
    local = values.rolling(5, center=True, min_periods=3).median()
    spikes = (values - local).abs() > spike_fraction * values.quantile(0.99)
    weekly = values.rolling("7D", center=True).median()
    dropouts = values < dropout_fraction * weekly
    return (spikes | dropouts).fillna(False).astype(bool)
