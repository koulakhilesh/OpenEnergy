"""GB interconnectors: capacity (NESO register), in-service dates and flows (Elexon), and
neighbouring markets' day-ahead prices (Ember)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from openenergy.data.ember import EmberPriceSource, _read
from openenergy.data.series import PriceSeries
from openenergy.errors import DataError

INTERCONNECTOR_ATTRIBUTION = (
    "Interconnectors: National Energy System Operator (NESO), Interconnector Register "
    "(https://www.neso.energy/data-portal/interconnector-register, 12 October 2026), NESO "
    "Open Data Licence v1.0 (https://www.neso.energy/data-portal/neso-open-licence), "
    "supported by National Energy SO Open Data; in-service dates and flows from Elexon BMRS "
    "FUELHH, contains BMRS data (c) Elexon Limited copyright and database right 2026; "
    "neighbouring day-ahead prices from Ember, European Wholesale Electricity Price Data "
    "(https://ember-energy.org/data/european-wholesale-electricity-price-data/), CC BY 4.0, "
    "converted to GBP with ECB euro reference rates (source: ECB). OpenEnergy is not "
    "affiliated with or endorsed by NESO, Elexon, Ember or the ECB."
)
REGISTER_FILE = "interconnectors.csv"
FLOWS_FILE = "interconnector_flows.csv"
NEIGHBOUR_FILE = "europe_day_ahead_ember.csv"
AVAILABILITY_FILE = "interconnector_availability.csv"
HOURLY_FLOWS_FILE = "interconnector_flows_hourly.csv"
GAP_FILE = "interconnector_gap_availability.csv"
# Lower edges (GBP/MWh) of the price-gap bins used by availability by gap.
GAP_EDGES = (0.0, 5.0, 10.0, 20.0, 40.0, 80.0)
# A link is in service from its first flow in the first 14 days that carry at least a
# fifth of its capacity, which skips months of commissioning test flows.
IN_SERVICE_DAYS = 14
IN_SERVICE_SHARE = 0.2


@dataclass(frozen=True)
class Interconnector:
    """One GB link: firm import and export capacity (TEC) and the day it entered service.

    ``in_service`` comes from the bundled Elexon flows (see ``IN_SERVICE_DAYS``), or is None
    if the link was already in service when the record starts. ``import_availability`` and
    ``export_availability`` are the shares of a price taker's trade the link actually made
    (``availability_from_flows``); 1 when no fitted file is present.
    """

    name: str
    neighbour: str
    import_mw: float
    export_mw: float
    in_service: pd.Timestamp | None
    import_availability: float = 1.0
    export_availability: float = 1.0


def interconnectors(system_dir: str | Path) -> list[Interconnector]:
    """Built links from ``interconnectors.csv`` with in-service dates from the flow record,
    and their availability from ``interconnector_availability.csv`` when present."""
    directory = Path(system_dir)
    register = directory / REGISTER_FILE
    if not register.is_file():
        raise DataError(f"interconnector register not found: {register}")
    table = pd.read_csv(register)
    flows = interconnector_flows(directory)
    fitted = _availability(directory)
    first_day = flows.index[0]
    links = []
    for row in table.to_dict("records"):
        name, fuel_type = str(row["link"]), str(row["bmrs_fuel_type"])
        import_mw, export_mw = float(row["import_mw"]), float(row["export_mw"])
        fuel = fuel_type.lower()
        imports, exports = f"{fuel}_import_mwh", f"{fuel}_export_mwh"
        if imports not in flows or exports not in flows:
            raise DataError(f"{name}: no flows for {fuel_type} in {FLOWS_FILE}")
        moved = flows[imports] + flows[exports]
        capacity = max(import_mw, export_mw) * 24 * IN_SERVICE_DAYS
        ahead = moved[::-1].rolling(IN_SERVICE_DAYS).sum()[::-1]
        busy = ahead.index[ahead >= IN_SERVICE_SHARE * capacity]
        if busy.empty:
            raise DataError(f"{name}: never in service in {FLOWS_FILE}")
        start = moved.index[(moved.index >= busy[0]) & (moved > 0)][0]
        imports_share, exports_share = fitted.get(name, (1.0, 1.0))
        links.append(
            Interconnector(
                name,
                str(row["neighbour"]),
                import_mw,
                export_mw,
                None if start == first_day else start,
                imports_share,
                exports_share,
            )
        )
    return links


def availability_from_flows(
    system_dir: str | Path,
    gb_prices: pd.Series[float],
    neighbours: NeighbourPriceSource,
) -> pd.DataFrame:
    """Per link, the share of a price taker's imports and exports that actually flowed.

    A price taker on ``gb_prices`` (actual hourly GBP/MWh, the fitting years) imports at
    full capacity whenever GB is dearer than the neighbour and exports whenever it is
    cheaper, from the day the link entered service. Each share is the actual energy
    (Elexon) over that trade, at most 1. Modelled prices are never used. Links with no
    trade in the period get the mean of the others.
    """
    directory = Path(system_dir)
    index = pd.DatetimeIndex(gb_prices.index)
    flows = interconnector_flows(directory)
    fuels = pd.read_csv(directory / REGISTER_FILE).set_index("link")["bmrs_fuel_type"].str.lower()
    days = flows[(flows.index >= index[0].normalize()) & (flows.index <= index[-1])]
    rows = []
    hours = float(pd.Timedelta(index[1] - index[0]) / pd.Timedelta(hours=1))
    for unit in interconnectors(directory):
        start = unit.in_service if unit.in_service is not None else index[0]
        live = index >= start
        imports = exports = 0
        if live.any():
            other = neighbours.prices(unit.neighbour, index[live]).prices
            imports = int((gb_prices[live] > other).sum())
            exports = int((gb_prices[live] < other).sum())
        moved = days[days.index >= start.normalize()]
        fuel = fuels[unit.name]
        rows.append(
            {
                "link": unit.name,
                "price_taker_import_mwh": imports * unit.import_mw * hours,
                "price_taker_export_mwh": exports * unit.export_mw * hours,
                "actual_import_mwh": float(moved[f"{fuel}_import_mwh"].sum()),
                "actual_export_mwh": float(moved[f"{fuel}_export_mwh"].sum()),
            }
        )
    table = pd.DataFrame(rows).set_index("link")
    for direction in ("import", "export"):
        trade = table[f"price_taker_{direction}_mwh"]
        share = (table[f"actual_{direction}_mwh"] / trade.where(trade > 0)).clip(upper=1.0)
        table[f"{direction}_availability"] = share.fillna(share.mean())
    return table


def _availability(directory: Path) -> dict[str, tuple[float, float]]:
    path = directory / AVAILABILITY_FILE
    if not path.is_file():
        return {}
    table = pd.read_csv(path)
    return {
        str(row["link"]): (float(row["import_availability"]), float(row["export_availability"]))
        for row in table.to_dict("records")
    }


def availability_by_gap(
    system_dir: str | Path,
    gb_prices: pd.Series[float],
    neighbours: NeighbourPriceSource,
) -> pd.DataFrame:
    """Per link and direction, the share of capacity used by size of the price gap.

    Hours from the day each link entered service are binned by the gap between
    ``gb_prices`` (actual hourly GBP/MWh) and the neighbour's actual price, from the
    lower edges in ``GAP_EDGES``: imports when GB is dearer, exports when cheaper. Each
    bin's share is the link's mean hourly flow that way (Elexon, hourly) over its
    capacity, made non-decreasing in the gap (weighted by hours) so that it can be offered
    as stepped capacity. Bins without hours take their neighbour's share. Modelled prices
    are never used. Columns: ``link``, ``direction``, ``gap_from``, ``share``, ``hours``.
    """
    directory = Path(system_dir)
    index = pd.DatetimeIndex(gb_prices.index)
    flows = interconnector_flows_hourly(directory)
    fuels = pd.read_csv(directory / REGISTER_FILE).set_index("link")["bmrs_fuel_type"].str.lower()
    edges = np.array(GAP_EDGES, dtype=float)
    rows = []
    for unit in interconnectors(directory):
        live = index >= (unit.in_service if unit.in_service is not None else index[0])
        if not live.any():
            continue
        gap = gb_prices[live] - neighbours.prices(unit.neighbour, index[live]).prices
        flow = flows[f"{fuels[unit.name]}_mw"].reindex(gap.index)
        frame = pd.DataFrame({"gap": gap, "flow": flow}).dropna()
        for direction, sign, capacity in (
            ("import", 1.0, unit.import_mw),
            ("export", -1.0, unit.export_mw),
        ):
            side = frame[sign * frame["gap"] > 0]
            bins = np.digitize(sign * side["gap"], edges) - 1
            used = (sign * side["flow"]).clip(lower=0) / capacity
            hours = np.array([(bins == k).sum() for k in range(len(edges))], dtype=float)
            means = pd.Series(
                [used[bins == k].mean() if hours[k] else np.nan for k in range(len(edges))]
            )
            shares = _non_decreasing(means.ffill().bfill().fillna(0.0).to_numpy(), hours)
            for edge, share, n in zip(edges, shares, hours, strict=True):
                rows.append(
                    {
                        "link": unit.name,
                        "direction": direction,
                        "gap_from": float(edge),
                        "share": float(min(max(share, 0.0), 1.0)),
                        "hours": int(n),
                    }
                )
    return pd.DataFrame(rows)


def gap_shares(system_dir: str | Path) -> dict[str, tuple[list[float], list[float]]]:
    """Import and export shares per gap bin (``GAP_EDGES``) from ``GAP_FILE``."""
    path = Path(system_dir) / GAP_FILE
    if not path.is_file():
        raise DataError(f"{GAP_FILE} not found; run scripts/fit_interconnector_availability.py")
    table = pd.read_csv(path).sort_values("gap_from")
    found = {}
    for link, rows in table.groupby("link"):
        imports = rows[rows["direction"] == "import"]["share"].tolist()
        exports = rows[rows["direction"] == "export"]["share"].tolist()
        if len(imports) != len(GAP_EDGES) or len(exports) != len(GAP_EDGES):
            raise DataError(f"{GAP_FILE}: {link} needs one share per gap bin and direction")
        found[str(link)] = (imports, exports)
    return found


def _non_decreasing(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Weighted pooled adjacent violators: the closest non-decreasing sequence."""
    blocks: list[list[float]] = []
    for value, weight in zip(values, weights, strict=True):
        blocks.append([float(value), float(weight), 1.0])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            v2, w2, n2 = blocks.pop()
            v1, w1, n1 = blocks.pop()
            total = w1 + w2
            blocks.append([(v1 * w1 + v2 * w2) / total if total else (v1 + v2) / 2, total, n1 + n2])
    return np.concatenate([[v] * int(n) for v, _, n in blocks])


def interconnector_flows_hourly(system_dir: str | Path) -> pd.DataFrame:
    """Hourly net flow per link from 2019, MW (positive into GB), columns ``<fuel type>_mw``."""
    path = Path(system_dir) / HOURLY_FLOWS_FILE
    if not path.is_file():
        raise DataError(f"hourly interconnector flows not found: {path}")
    frame = pd.read_csv(path, index_col="utc_timestamp")
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, format="ISO8601"))
    return frame


def interconnector_flows(system_dir: str | Path) -> pd.DataFrame:
    """Daily MWh per link, columns ``<fuel type>_import_mwh`` and ``_export_mwh``."""
    path = Path(system_dir) / FLOWS_FILE
    if not path.is_file():
        raise DataError(f"interconnector flows not found: {path}")
    frame = pd.read_csv(path, index_col="date")
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index)).tz_localize("UTC")
    return frame.fillna(0.0)


class NeighbourPriceSource:
    """Reads ``europe_day_ahead_ember.csv`` (EUR/MWh) and converts with the ECB rate file."""

    def __init__(self, path: str | Path, rates: str | Path | None = None) -> None:
        self.path = Path(path)
        self.rates = (
            Path(rates) if rates is not None else self.path.with_name("ecb_gbp_per_eur.csv")
        )

    def prices(
        self, neighbour: str, index: pd.DatetimeIndex, max_gap_hours: int = 3
    ) -> PriceSeries:
        """GBP/MWh on ``index``; gaps up to ``max_gap_hours`` are interpolated."""
        eur = _read(self.path, "utc_timestamp", neighbour)
        eur.index = pd.DatetimeIndex(pd.to_datetime(eur.index, utc=True, format="ISO8601"))
        hourly = eur[~eur.index.duplicated()].sort_index().asfreq("h")
        hourly = hourly.interpolate(limit=max_gap_hours, limit_area="inside")
        values = hourly.reindex(index.floor("h")).set_axis(index)
        if values.isna().any():
            first = values.index[values.isna()][0]
            raise DataError(f"no {neighbour} price around {first} in {self.path.name}")
        rate = EmberPriceSource(self.path, self.rates)._rate(index)
        return PriceSeries(values * rate, currency="GBP", zone=neighbour)
