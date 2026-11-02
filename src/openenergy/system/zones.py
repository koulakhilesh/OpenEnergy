"""Two zones: Scotland and England & Wales, joined by the B6 boundary (needs the system
extra). See ``ZONES_NOTE`` for the method.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from openenergy.backtest.reference import perfect_foresight_run
from openenergy.errors import ConfigError, DataError
from openenergy.metrics.summary import summarise
from openenergy.system.model import SystemSpec

SCOTLAND, SOUTH = "scotland", "england_wales"
BOUNDARY = "SCOTEX"
ZONES_NOTE = (
    "Two zones: GB's system split into Scotland and England and Wales. Each hour's demand is "
    "split by NESO's zonal demand; each generator by its technology's share of capacity in "
    "Scotland that year (wind and solar from the Renewable Energy Planning Database; thermal, "
    "nuclear, hydro, pumped storage and biomass from DUKES); historic imports and other "
    "generation stay in England and Wales. Both zones keep GB's hourly wind and solar shape. "
    "The boundary carries up to NESO's monthly mean day-ahead limit on the Scottish export "
    "boundary (SCOTEX). Nothing is fitted to the recorded flows, which only check the result."
)
# DUKES rows behind each generator technology of ``build_system``.
PLANT = {
    "nuclear": ("nuclear",),
    "biomass": ("bioenergy",),
    "hydro": ("hydro",),
    "pumped_storage": ("pumped_storage",),
    "ccgt": ("ccgt",),
    "coal": ("coal",),
    "peaking": ("gas_turbine", "oil_engine"),
}
REPD = {"wind": ("onshore_wind", "offshore_wind"), "solar": ("solar",)}


@dataclass(frozen=True, eq=False)
class TwoZones:
    """Hourly zone prices (GBP/MWh), the boundary limit and the transfer from Scotland (MW),
    modelled and recorded."""

    frame: pd.DataFrame
    shares: dict[str, float]


def boundary_limit(
    zones_dir: str | Path, index: pd.DatetimeIndex, limit: float | Literal["scotex", "recorded"]
) -> pd.Series[float]:
    """The B6 limit (MW) each period: a number, NESO's monthly mean day-ahead SCOTEX limit, or
    the largest transfer recorded that year."""
    if not isinstance(limit, str):
        if not limit > 0:
            raise ConfigError(f"the boundary limit must be positive, got {limit}")
        return pd.Series(float(limit), index=index)
    if limit == "recorded":
        recorded = zone_demand(zones_dir, index)["transfer"].abs().max()
        if not recorded > 0:
            raise DataError("no recorded transfer in this period; give a limit in MW")
        return pd.Series(float(recorded), index=index)
    table = _read(Path(zones_dir).parent / "constraints/day_ahead_boundaries_monthly.csv")
    monthly = table[table["group"] == BOUNDARY].set_index("month")["limit_mw"]
    months = pd.DatetimeIndex(index).tz_convert(None).strftime("%Y-%m")
    values = monthly.reindex(months).to_numpy(dtype=np.float64)
    if np.isnan(values).any():
        first = months[np.isnan(values)][0]
        raise DataError(f"no {BOUNDARY} limit for {first}; give a limit in MW or 'recorded'")
    return pd.Series(values, index=index)


def scottish_shares(zones_dir: str | Path, year: int) -> dict[str, float]:
    """Scotland's share of each technology's GB capacity, mid-``year``."""
    directory = Path(zones_dir)
    plant = _read(directory / "plant_by_zone.csv")
    repd = _read(directory / "capacity_by_year.csv")
    shares = {name: _share(plant, rows, year) for name, rows in PLANT.items()}
    shares.update({name: _share(repd, rows, year) for name, rows in REPD.items()})
    shares["imports"] = shares["other"] = 0.0
    return shares


def zone_demand(zones_dir: str | Path, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Scotland's share of demand and the recorded transfer from Scotland, on ``index``."""
    frame = _read(Path(zones_dir) / "demand_by_zone.csv")
    stamps = pd.DatetimeIndex(pd.to_datetime(frame["utc_timestamp"], utc=True))
    step = index[1] - index[0] if len(index) > 1 else pd.Timedelta(hours=1)
    values = (
        pd.DataFrame(
            {
                "share": frame["scotland_demand_mw"].to_numpy()
                / frame["national_demand_mw"].to_numpy(),
                "transfer": frame["scottish_transfer_mw"].to_numpy(dtype=np.float64),
            },
            index=stamps,
        )
        .resample(step)
        .mean()
    )
    out = values.reindex(index)
    if out["share"].isna().any():
        missing = index[out["share"].isna().to_numpy()]
        raise DataError(f"no zone demand from {missing[0]} ({len(missing)} periods)")
    return out


def solve_two_zones(
    spec: SystemSpec,
    zones_dir: str | Path,
    limit: float | Literal["scotex", "recorded"] = "scotex",
) -> TwoZones:
    """Least-cost dispatch of ``spec`` on two zones; prices are each zone's marginal cost."""
    from openenergy.system._pypsa import dispatch_two_zones

    index = pd.DatetimeIndex(spec.demand.index)
    years = set(index.year)
    if len(years) != 1:
        raise ConfigError(f"solve one calendar year at a time, got {sorted(years)}")
    shares = scottish_shares(zones_dir, years.pop())
    zones = zone_demand(zones_dir, index)
    limit_mw = boundary_limit(zones_dir, index, limit)
    solved = dispatch_two_zones(spec, (SCOTLAND, SOUTH), shares, zones["share"], limit_mw)
    frame = pd.DataFrame(
        {
            "price_scotland": solved[f"price_{SCOTLAND}"],
            "price_england_wales": solved[f"price_{SOUTH}"],
            "limit_mw": limit_mw,
            "transfer_model_mw": solved["transfer_mw"],
            "transfer_actual_mw": zones["transfer"],
        },
        index=index,
    )
    return TwoZones(frame, shares)


def compare(result: TwoZones) -> dict[str, float]:
    """Modelled against recorded transfer, and how often the zones' prices split."""
    frame = result.frame
    both = frame.dropna(subset=["transfer_actual_mw"])
    model, actual = both["transfer_model_mw"], both["transfer_actual_mw"]
    gap = frame["price_england_wales"] - frame["price_scotland"]
    at_limit = frame["transfer_model_mw"].abs() >= frame["limit_mw"] - 1e-6
    near = both["transfer_actual_mw"].abs() >= 0.9 * both["limit_mw"]
    return {
        "limit_mw": float(frame["limit_mw"].mean()),
        "transfer_mean_model": float(model.mean()) if len(both) else float("nan"),
        "transfer_mean_actual": float(actual.mean()) if len(both) else float("nan"),
        "correlation": float(np.corrcoef(model, actual)[0, 1]) if len(both) > 1 else float("nan"),
        "model_at_limit_share": float(at_limit.mean()),
        "actual_near_limit_share": float(near.mean()) if len(both) else float("nan"),
        "price_split_share": float((gap.abs() > 1.0).mean()),
        "price_gap_mean": float(gap.mean()),
        "scotland_wind_share": result.shares["wind"],
    }


def battery_values(result: TwoZones) -> dict[str, float]:
    """Revenue per MW-year of the reference battery with perfect foresight on each zone's
    modelled price."""
    return {
        zone: summarise(perfect_foresight_run(result.frame[f"price_{zone}"])).revenue_per_mw_year
        or 0.0
        for zone in (SCOTLAND, SOUTH)
    }


def _share(table: pd.DataFrame, rows: tuple[str, ...], year: int) -> float:
    part = table[table["technology"].isin(rows)]
    by_zone = part.pivot_table(index="year", columns="zone", values="mw", aggfunc="sum")
    if year not in by_zone.index or year - 1 not in by_zone.index:
        raise DataError(
            f"no zone capacity for {', '.join(rows)} at the end of {year - 1} and {year}"
        )
    middle = by_zone.reindex(columns=[SCOTLAND, SOUTH]).fillna(0.0).loc[[year - 1, year]]
    scotland, south = middle.to_numpy(dtype=np.float64).mean(axis=0)
    total = float(scotland + south)
    return float(scotland) / total if total > 0 else 0.0


def _read(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise DataError(f"zone data not found: {path} (run scripts/fetch_zones.py)")
    return pd.read_csv(path)
