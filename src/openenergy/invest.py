"""Battery investment case: what a 1 MW / 2 MWh battery is worth over its life.

Each case assumes every year of the battery's life pays like one year OpenEnergy has seen
or modelled: what GB's real batteries made (energy and frequency response), what the
optimiser makes on the day-ahead market with OpenEnergy's forecast, or what a battery
joining NESO's FES 2035 fleet makes on modelled prices. The Capacity Market pays on top,
at the latest four-year-ahead clearing price and de-rating factor. Costs are NREL's
Annual Technology Baseline for US utility-scale batteries, converted to pounds: GB costs
differ, so a cost scale is offered. The spread of the cases, not any one value, is the
result.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from openenergy.errors import ConfigError, DataError

HOURS = 2
MW_PER_KW = 1000.0
INVEST_ATTRIBUTION = (
    "Battery costs: NREL, 2024 Annual Technology Baseline (https://atb.nrel.gov/), "
    "utility-scale battery storage, Moderate scenario, market case, licensed under CC BY 4.0 "
    "(https://creativecommons.org/licenses/by/4.0/); converted from 2022 US dollars at the "
    "ECB's 2022 average rates (source: ECB). Capacity Market: NESO Capacity Market Register, "
    "auction results and de-rating factors (https://www.neso.energy/data-portal/"
    "capacity-market-register), NESO Open Data Licence v1.0, supported by National Energy SO "
    "Open Data. OpenEnergy is not affiliated with or endorsed by NREL, the ECB or NESO."
)


@dataclass(frozen=True)
class Costs:
    """For a 1 MW / 2 MWh battery built in ``year``, in pounds."""

    year: int
    capex_gbp: float
    fixed_om_gbp_per_year: float


@dataclass(frozen=True)
class CapacityMarket:
    auction: str
    clearing_gbp_per_kw_year: float
    derating_factor: float

    @property
    def gbp_per_mw_year(self) -> float:
        return self.clearing_gbp_per_kw_year * MW_PER_KW * self.derating_factor


def battery_costs(directory: Path, year: int, scale: float = 1.0) -> Costs:
    """ATB's capital and fixed O&M cost of a 2-hour battery built in ``year``, times ``scale``."""
    table = _read(directory / "battery_costs.csv")
    row = table[(table["duration_hours"] == HOURS) & (table["year"] == year)]
    if row.empty:
        years = table.loc[table["duration_hours"] == HOURS, "year"]
        raise ConfigError(f"no battery cost for {year}; choose {years.min()} to {years.max()}")
    r = row.iloc[0]
    per_mw = MW_PER_KW * float(r["gbp_per_usd_2022"]) * scale
    return Costs(
        year,
        float(r["capex_usd2022_per_kw"]) * per_mw,
        float(r["fixed_om_usd2022_per_kw_year"]) * per_mw,
    )


def capacity_market(directory: Path, price: float | None = None) -> CapacityMarket:
    """The latest four-year-ahead auction with a clearing price and its 2-hour de-rating."""
    auctions = _read(directory / "capacity_market_auctions.csv")
    factors = _read(directory / "capacity_market_storage_derating.csv")
    t4 = auctions[auctions["type"] == "T-4"].sort_values("delivery_year", ascending=False)
    for auction, clearing in zip(t4["auction"], t4["clearing_gbp_per_kw_year"], strict=True):
        match = factors[(factors["auction"] == auction) & (factors["duration_hours"] == HOURS)]
        if not match.empty:
            return CapacityMarket(
                str(auction),
                float(clearing) if price is None else price,
                float(match["derating_factor"].iloc[0]),
            )
    raise DataError("no four-year-ahead auction with a 2-hour storage de-rating factor")


def revenue_cases(data: Path) -> pd.DataFrame:
    """Revenue per MW-year (GBP) of each case: ``family``, ``case``, ``revenue``."""
    real = _read(data / "fleet/real_vs_model.csv").set_index("year")
    rows = [
        (
            "Real batteries, energy and response",
            str(year),
            real.loc[year, "real_total_with_response_per_mw_year"],
        )
        for year in real.index
        if year >= 2023
    ]
    rows += [
        (
            "Model, day-ahead with OpenEnergy's forecast",
            str(year),
            real.loc[year, "model_2h_fundamentals_per_mw_year"],
        )
        for year in real.index
    ]
    saturation = _read(data / "scenarios/saturation_years.csv")
    fleet = saturation[saturation["battery_scale"] == 1.0]
    rows += [
        (
            "Model, FES 2035 with NESO's battery fleet",
            f"{r.pathway}, {r.weather_year} weather",
            r.revenue_per_mw_year,
        )
        for r in fleet.itertuples()
    ]
    return pd.DataFrame(rows, columns=["family", "case", "revenue"]).astype({"revenue": float})


def appraise(
    cases: pd.DataFrame, costs: Costs, market: CapacityMarket, life: int, rate: float
) -> pd.DataFrame:
    """Each case's yearly cash flow, net present value at ``rate``, internal rate of return
    and break-even cost (the build cost per MW at which the net present value is zero)."""
    if life < 1:
        raise ConfigError(f"life must be at least one year, got {life}")
    if not -1 < rate < 1:
        raise ConfigError(f"rate must be between -1 and 1, got {rate}")
    out = cases.copy()
    out["capacity_market"] = market.gbp_per_mw_year
    out["fixed_om"] = -costs.fixed_om_gbp_per_year
    out["net"] = out["revenue"] + out["capacity_market"] + out["fixed_om"]
    out["breakeven_capex"] = out["net"] * _annuity(life, rate)
    out["npv"] = out["breakeven_capex"] - costs.capex_gbp
    out["irr"] = [irr(costs.capex_gbp, net, life) for net in out["net"]]
    return out


def npv(capex: float, net: float, life: int, rate: float) -> float:
    """Net present value of paying ``capex`` now for ``net`` at the end of each year."""
    return -capex + net * _annuity(life, rate)


def irr(capex: float, net: float, life: int) -> float:
    """The rate at which the net present value is zero; NaN if the battery never pays back."""
    if net * life < capex:
        return float("nan")
    low, high = 0.0, 10.0
    for _ in range(100):
        mid = (low + high) / 2
        if npv(capex, net, life, mid) > 0:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def _annuity(life: int, rate: float) -> float:
    if rate == 0:
        return float(life)
    return float((1 - (1 + rate) ** -life) / rate)


def _read(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise DataError(f"investment input not found: {path} (run scripts/fetch_invest.py)")
    return pd.read_csv(path)


def summary(table: pd.DataFrame) -> pd.DataFrame:
    """Median and range of the break-even cost, NPV and IRR by family."""
    return table.groupby("family", sort=False).agg(
        cases=("case", "size"),
        revenue_median=("revenue", "median"),
        breakeven_min=("breakeven_capex", "min"),
        breakeven_median=("breakeven_capex", "median"),
        breakeven_max=("breakeven_capex", "max"),
        npv_median=("npv", "median"),
        irr_median=("irr", lambda s: float(np.nanmedian(s)) if s.notna().any() else float("nan")),
        pays_back=("irr", lambda s: int(s.notna().sum())),
        worth_building=("npv", lambda s: int((s > 0).sum())),
    )
