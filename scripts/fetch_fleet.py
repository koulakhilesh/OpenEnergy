"""Fetch what GB's grid batteries actually did into data/fleet/.

From Elexon's BMRS Insights API (BMRS data licence; contains BMRS data (c) Elexon Limited
copyright and database right 2026):

- battery_units.csv: the BM units in Elexon's register whose name or lead party names a
  battery ("battery", "BESS", "energy storage"), excluding pumped storage, transmission (T_)
  and embedded (E_) units only, with registered capacity and GSP group;
- battery_daily.csv: for each unit and UTC day with a non-zero physical notification (PN),
  energy exported and imported by its PN (MWh), the PN valued at the GB day-ahead price
  (Ember, bundled) and at the system (imbalance) price (Elexon, bundled), GBP; and its
  Balancing Mechanism indicative cashflows (EBOCF) for accepted offers and bids by
  settlement date (UK local day), GBP;
- fleet_hourly.csv: the sum of all battery units' PN each UTC hour (MW, positive exporting),
  exports and imports separately, and the number of units with a non-zero PN.

A PN is a unit's final physical position at gate closure, an hour before delivery: it
reflects trades on every market up to then, not where they were made. Balancing Mechanism
actions after gate closure are in the cashflows, not in the PN; frequency response
contracts are in neither. Raw API responses are cached (``--cache``) so reruns are quick.

Run: uv run python scripts/fetch_fleet.py
"""

import argparse
import hashlib
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from functools import partial
from pathlib import Path

import pandas as pd

from openenergy.data.ember import gb_prices

ROOT = Path(__file__).parents[1]
OUT = ROOT / "data/fleet"
API = "https://data.elexon.co.uk/bmrs/api/v1"
NAMED = re.compile(r"batter|bess\b|energy stor", re.IGNORECASE)
PRICES = ROOT / "data/prices/gb_day_ahead_ember.csv"
SYSTEM = ROOT / "data/balancing/gb_system_prices.csv"


def get(url: str, cache: Path | None) -> dict:
    path = cache / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".json") if cache else None
    if path is not None and path.is_file():
        return json.loads(path.read_text())
    request = urllib.request.Request(url, headers={"User-Agent": "OpenEnergy"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = json.load(response)
            break
        except OSError:
            if attempt == 4:
                raise
            time.sleep(2**attempt)
    if path is not None:
        path.write_text(json.dumps(body))
    return body


def units(cache: Path) -> pd.DataFrame:
    register = get(f"{API}/reference/bmunits/all", cache)
    rows = [
        u
        for u in register
        if NAMED.search(f"{u.get('bmUnitName') or ''} {u.get('leadPartyName') or ''}")
        and u.get("fuelType") not in ("PS", "CCGT", "OCGT", "COAL", "NUCLEAR")
        and u.get("bmUnitType") in ("T", "E")
    ]
    # Transmission units have no GSP group; each TLF zone has one loss factor, so place them
    # by matching their transmission loss factor with units whose GSP group is known.
    region_of = {
        round(float(u["transmissionLossFactor"]), 5): u["gspGroupName"]
        for u in register
        if u.get("gspGroupName") and u.get("transmissionLossFactor") is not None
    }
    regions = [
        u.get("gspGroupName")
        or region_of.get(round(float(u.get("transmissionLossFactor") or 0), 5), "")
        for u in rows
    ]
    frame = pd.DataFrame(
        {
            "unit": [u["elexonBmUnit"] for u in rows],
            "national_grid_unit": [u.get("nationalGridBmUnit") for u in rows],
            "name": [u.get("bmUnitName") for u in rows],
            "lead_party": [u.get("leadPartyName") for u in rows],
            "type": [u.get("bmUnitType") for u in rows],
            "generation_capacity_mw": [float(u.get("generationCapacity") or 0) for u in rows],
            "demand_capacity_mw": [abs(float(u.get("demandCapacity") or 0)) for u in rows],
            "gsp_group": [u.get("gspGroupName") or "" for u in rows],
            "transmission_loss_factor": [u.get("transmissionLossFactor") for u in rows],
            "region": regions,
            "zone": [
                "scotland" if r.endswith("Scotland") else "england_wales" if r else ""
                for r in regions
            ],
        }
    )
    return frame.sort_values("unit").reset_index(drop=True)


def weeks(start: date, end: date) -> list[tuple[date, date]]:
    """[first, last] day pairs of at most seven days (the API's longest range)."""
    out = []
    day = start
    while day < end:
        last = min(day + timedelta(days=6), end - timedelta(days=1))
        out.append((day, last))
        day = last + timedelta(days=1)
    return out


def pn(week: tuple[date, date], unit_ids: list[str], cache: Path) -> pd.DataFrame:
    """Mean PN (MW) each half-hour and unit, time-weighted over the PN's points."""
    first, last = week
    units = "".join(f"&bmUnit={u}" for u in unit_ids)
    url = (
        f"{API}/datasets/PN/stream?from={first}T00:00Z&to={last + timedelta(days=1)}T00:00Z{units}"
    )
    frame = pd.DataFrame(get(url, cache))
    if frame.empty:
        return pd.DataFrame(columns=["slot", "unit", "mw"])
    frame = frame.drop_duplicates(["bmUnit", "timeFrom", "timeTo", "levelFrom", "levelTo"])
    t0 = pd.to_datetime(frame["timeFrom"], utc=True)
    t1 = pd.to_datetime(frame["timeTo"], utc=True)
    frame["energy"] = (frame["levelFrom"] + frame["levelTo"]) / 2 * (t1 - t0).dt.total_seconds()
    frame["slot"] = t0.dt.floor("30min")
    grouped = frame.groupby(["slot", "bmUnit"])["energy"].sum() / 1800
    return grouped.rename("mw").rename_axis(["slot", "unit"]).reset_index()


def metered(week: tuple[date, date], unit_ids: list[str], cache: Path) -> pd.DataFrame:
    """Metered output (MWh, export positive) each half-hour and unit, latest settlement run."""
    first, last = week
    units = "".join(f"&bmUnit={u}" for u in unit_ids)
    frame = pd.DataFrame(get(f"{API}/datasets/B1610/stream?from={first}&to={last}{units}", cache))
    if frame.empty:
        return pd.DataFrame(columns=["slot", "unit", "mwh"])
    frame["slot"] = [
        settlement_start(d, p)
        for d, p in zip(frame["settlementDate"], frame["settlementPeriod"], strict=True)
    ]
    grouped = frame.groupby(["slot", "bmUnit"])["quantity"].last()
    return grouped.rename("mwh").rename_axis(["slot", "unit"]).reset_index()


def cashflows(day: date, cache: Path, wanted: set[str]) -> list[tuple[str, str, str, float, float]]:
    """Accepted BM volumes (MWh, before tagging) and indicative cashflows (GBP) by half-hour."""
    kept = cache / f"bm_{day}.json"
    if kept.is_file():
        return [tuple(r) for r in json.loads(kept.read_text())]  # type: ignore[misc]
    rows = []
    units = "".join(f"&bmUnit={u}" for u in sorted(wanted))
    for side in ("offer", "bid"):
        money = get(
            f"{API}/balancing/settlement/indicative/cashflows/all/{side}/{day}?format=json{units}",
            None,
        )
        volume = get(
            f"{API}/balancing/settlement/indicative/volumes/all/{side}/{day}?format=json{units}",
            None,
        )
        accepted = {
            (r["bmUnit"], r["startTime"]): float(r["totalVolumeAccepted"] or 0)
            for r in volume["data"]
            if r["bmUnit"] in wanted and r["dataType"] == "Original"
        }
        for r in money["data"]:
            if r["bmUnit"] in wanted and r.get("totalCashflow") is not None:
                key = (r["bmUnit"], r["startTime"])
                rows.append(
                    (
                        r["startTime"],
                        r["bmUnit"],
                        side,
                        float(r["totalCashflow"]),
                        accepted.pop(key, 0.0),
                    )
                )
        rows.extend((t, unit, side, 0.0, mwh) for (unit, t), mwh in accepted.items())
    kept.write_text(json.dumps(rows))
    return rows


def settlement_start(day: str, period: int) -> pd.Timestamp:
    """UTC start of a settlement period: periods count half-hours from UK local midnight."""
    midnight = pd.Timestamp(day).tz_localize("Europe/London").tz_convert("UTC")
    return midnight + pd.Timedelta(minutes=30 * (int(period) - 1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, default=date(2021, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 30))
    parser.add_argument("--cache", type=Path, default=Path("/tmp/openenergy-fleet"))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    register = units(args.cache)
    register.to_csv(OUT / "battery_units.csv", index=False)
    print(f"battery_units.csv: {len(register)} units")

    ids = register["unit"].tolist()
    spans = weeks(args.start, args.end)
    with ThreadPoolExecutor(args.workers) as pool:
        notified = pd.concat(list(pool.map(lambda w: pn(w, ids, args.cache), spans)))
        meters = pd.concat(list(pool.map(lambda w: metered(w, ids, args.cache), spans)))
    first, stop = pd.Timestamp(args.start, tz="UTC"), pd.Timestamp(args.end, tz="UTC")
    half_hours = pd.date_range(first, stop, freq="30min", inclusive="left")
    wide = partial(pd.DataFrame.pivot_table, index="slot", columns="unit", aggfunc="sum")
    mw = wide(notified, values="mw").reindex(half_hours)
    out = wide(meters, values="mwh").reindex(half_hours)
    ran = sorted(
        set(mw.columns[(mw.fillna(0).abs() > 0).any()])
        | set(out.columns[(out.fillna(0).abs() > 0).any()])
    )
    mw, out = mw.reindex(columns=ran), out.reindex(columns=ran)
    print(f"{len(ran)} units with a non-zero PN or metered output, {len(half_hours)} half-hours")

    peak = (out.abs() * 2).max()
    register["capacity_mw"] = [
        g if g > 0 else d if d > 0 else round(float(peak.get(u, 0) or 0), 1)
        for u, g, d in zip(
            register["unit"],
            register["generation_capacity_mw"],
            register["demand_capacity_mw"],
            strict=True,
        )
    ]
    register["capacity_source"] = [
        "generation" if g > 0 else "demand" if d > 0 else "metered peak"
        for g, d in zip(
            register["generation_capacity_mw"], register["demand_capacity_mw"], strict=True
        )
    ]
    register.to_csv(OUT / "battery_units.csv", index=False)

    wanted = set(register["unit"])
    days = pd.date_range(args.start, args.end - timedelta(days=1)).date
    with ThreadPoolExecutor(args.workers) as pool:
        found = [
            row
            for rows in pool.map(lambda d: cashflows(d, args.cache, wanted), days)
            for row in rows
        ]
    bm = pd.DataFrame(found, columns=["time", "unit", "side", "gbp", "mwh"])
    bm["time"] = pd.to_datetime(bm["time"], utc=True)
    bm = bm[(bm["time"] >= first) & (bm["time"] < stop)]

    def table(side: str, value: str) -> pd.DataFrame:
        rows = bm[bm["side"] == side]
        wide = rows.pivot_table(index="time", columns="unit", values=value, aggfunc="sum")
        return wide.reindex(index=half_hours, columns=ran)

    offer_gbp, bid_gbp = table("offer", "gbp"), table("bid", "gbp")
    offer_mwh, bid_mwh = table("offer", "mwh"), table("bid", "mwh")

    day_ahead = gb_prices([PRICES], args.start, args.end - timedelta(days=1))[0].prices
    day_ahead = day_ahead.reindex(half_hours.floor("h")).set_axis(half_hours)
    system = pd.read_csv(SYSTEM, index_col=0).iloc[:, 0]
    system.index = pd.to_datetime(system.index, utc=True)
    system = system.reindex(half_hours)

    contracted = mw * 0.5
    # What the meter recorded beyond the PN and the accepted BM volumes settles as imbalance.
    imbalance = out.fillna(0) - contracted.fillna(0) - offer_mwh.fillna(0) - bid_mwh.fillna(0)
    columns = {
        "pn_mwh_out": contracted.clip(lower=0),
        "pn_mwh_in": -contracted.clip(upper=0),
        "pn_value_day_ahead_gbp": contracted.mul(day_ahead, axis=0),
        "metered_mwh_out": out.clip(lower=0),
        "metered_mwh_in": -out.clip(upper=0),
        "metered_value_day_ahead_gbp": out.mul(day_ahead, axis=0),
        "bm_offer_mwh": offer_mwh,
        "bm_bid_mwh": bid_mwh,
        "bm_offer_gbp": offer_gbp,
        "bm_bid_gbp": bid_gbp,
        "imbalance_mwh": imbalance.where(out.notna()),
        "imbalance_gbp": imbalance.where(out.notna()).mul(system, axis=0),
    }
    day = half_hours.strftime("%Y-%m-%d")
    daily = pd.concat(
        {name: frame.groupby(day).sum(min_count=1).stack() for name, frame in columns.items()},
        axis=1,
    )
    daily.index = daily.index.set_names(["date", "unit"])
    moved = (
        daily[["pn_mwh_out", "pn_mwh_in", "metered_mwh_out", "metered_mwh_in"]]
        .fillna(0)
        .sum(axis=1)
    )
    daily = daily[moved > 0].round(3)
    daily.reset_index().to_csv(OUT / "battery_daily.csv", index=False)
    print(f"battery_daily.csv: {len(daily)} unit-days")

    meter = out.where(out.notna(), mw * 0.5) * 2  # MW: metered where published, else the PN
    hourly = (
        pd.DataFrame(
            {
                "metered_net_mw": (out * 2).sum(axis=1, min_count=1),
                "pn_net_mw": mw.sum(axis=1, min_count=1),
                "export_mw": meter.clip(lower=0).sum(axis=1, min_count=1),
                "import_mw": (-meter.clip(upper=0)).sum(axis=1, min_count=1),
                "units": (meter.fillna(0).abs() > 0).sum(axis=1),
            }
        )
        .resample("h")
        .mean()
    )
    hourly.index = hourly.index.strftime("%Y-%m-%dT%H:%M:%SZ")
    hourly.round(2).rename_axis("utc_timestamp").to_csv(OUT / "fleet_hourly.csv")
    print(f"fleet_hourly.csv: {len(hourly)} hours")


if __name__ == "__main__":
    main()
