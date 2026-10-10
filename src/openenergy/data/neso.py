"""GB half-hourly generation by fuel from NESO's historic generation mix extract."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from openenergy.data.series import _between, _validate
from openenergy.errors import DataError

MIX_ATTRIBUTION = (
    "Generation mix: National Energy System Operator (NESO), Historic generation mix and "
    "carbon intensity, https://www.neso.energy/data-portal/historic-generation-mix, NESO "
    "Open Data Licence v1.0. Supported by National Energy SO Open Data. Changes: derived "
    "columns dropped, half-hours averaged to the analysis step. OpenEnergy is not "
    "affiliated with or endorsed by NESO."
)
FUELS = (
    "gas", "coal", "nuclear", "wind", "wind_emb", "hydro", "imports", "biomass", "other",
    "solar", "storage",
)  # fmt: skip
TOTAL = "generation"
# NESO rounds each fuel to whole MW, so the published total can differ from the sum by a few.
_SUM_TOLERANCE_MW = 5.0


class GenerationMixSource:
    """Reads the ``utc_timestamp, <fuels>, generation`` CSV written by the fetch script."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def mix(
        self,
        start: date | None = None,
        end: date | None = None,
        step: pd.Timedelta | None = None,
    ) -> pd.DataFrame:
        """Generation by fuel and in total (MW) over whole UTC days, ``start``/``end`` inclusive.

        Averaging to a coarser ``step`` leaves an interval missing unless every half-hour
        in it is present.
        """
        if not self.path.is_file():
            raise DataError(f"generation mix file not found: {self.path}")
        frame = pd.read_csv(self.path)
        missing = sorted({"utc_timestamp", *FUELS, TOTAL} - set(frame.columns))
        if missing:
            raise DataError(f"{self.path.name} is missing columns: {', '.join(missing)}")
        index = pd.DatetimeIndex(pd.to_datetime(frame["utc_timestamp"], utc=True, format="ISO8601"))
        mix = pd.DataFrame(frame[[*FUELS, TOTAL]].to_numpy(dtype=float), index=index)
        mix.columns = pd.Index([*FUELS, TOTAL])
        _validate(mix[TOTAL])
        if (mix < 0).any().any():
            raise DataError(f"{self.path.name} has negative generation")
        mismatch = (mix[list(FUELS)].sum(axis=1) - mix[TOTAL]).abs().max()
        if mismatch > _SUM_TOLERANCE_MW:
            raise DataError(f"fuels do not add up to {TOTAL} (off by up to {mismatch:.0f} MW)")
        if start is not None or end is not None:
            kept = _between(mix[TOTAL], start, end, "GB").index
            mix = mix.loc[kept]
        if step is None:
            return mix
        native = mix.index[1] - mix.index[0]
        if step < native or step % native != pd.Timedelta(0):
            raise DataError(f"step {step} must be a multiple of the data step {native}")
        grouped = mix.resample(step)
        return grouped.mean().where(grouped.count() == int(step / native))
