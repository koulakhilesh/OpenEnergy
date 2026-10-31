"""Write the static data the web app's in-browser pages use, into web/public/data/.

Model output and reshaped copies of bundled data, so the Battery Lab, Grid replay, 2035 and
Beat the battery pages need no server:

- prices-YYYY.json (2019 to the last price year): hourly GB day-ahead price (Ember) and the
  fundamentals forecast for every UTC hour of the year, with the last week of the year
  before so last week's prices can be read from the first day;
- mix-YYYY.json (2019-2025): hourly generation by fuel (NESO historic generation mix) and
  carbon intensity (NESO Carbon Intensity API);
- saturation.json: the storage saturation study (data/scenarios/saturation.csv);
- engine-parity.json (in web/src/engine/): one month of prices and forecasts with what the
  Python backtest earns each day, for the TypeScript engine's parity test.

Every file carries the attribution of the data it holds.

Run: uv run python scripts/build_app_data.py
"""

import json
import math
from datetime import date
from pathlib import Path

import pandas as pd

from openenergy.assets import BatterySpec
from openenergy.backtest import BacktestConfig, run_backtest
from openenergy.data.carbon import CARBON_ATTRIBUTION, CarbonIntensitySource
from openenergy.data.ember import EMBER_ATTRIBUTION, gb_prices
from openenergy.data.fundamentals import FUNDAMENTALS_ATTRIBUTION
from openenergy.data.neso import MIX_ATTRIBUTION, GenerationMixSource
from openenergy.dispatch import DispatchConfig
from openenergy.forecast import NaiveLastWeek, PerfectForesight, PrecomputedForecast

ROOT = Path(__file__).parents[1]
DATA = ROOT / "data"
OUT = ROOT / "web/public/data"
PRICES = DATA / "prices/gb_day_ahead_ember.csv"
FORECAST = DATA / "forecasts/gb_fundamentals_day_ahead.csv"
FIRST_YEAR = 2019
MIX_LAST_YEAR = 2025
FORECAST_NOTE = (
    "Fundamentals forecast: OpenEnergy model output (data/forecasts), made at noon UTC the "
    "day before from what was known then. " + FUNDAMENTALS_ATTRIBUTION
)
# Fuels shown in the replay, in stacking order; embedded wind joins wind.
FUELS = ("nuclear", "biomass", "hydro", "wind", "solar", "imports", "storage", "gas", "coal")
PARITY_MONTH = (date(2025, 1, 1), date(2025, 1, 31))


def values(series: pd.Series, index: pd.DatetimeIndex, digits: int = 2) -> list[float | None]:
    out = series.reindex(index).round(digits)
    return [None if math.isnan(v) else float(v) for v in out]


def hours(year: int) -> pd.DatetimeIndex:
    return pd.date_range(f"{year}-01-01", f"{year}-12-31 23:00", freq="h", tz="UTC")


def write(name: str, payload: dict[str, object], folder: Path = OUT) -> None:
    path = folder / name
    path.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False))
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1000:.0f} kB)")


def prices() -> pd.Series:
    return gb_prices([PRICES], date(FIRST_YEAR - 1, 12, 1), None)[0].prices


def price_files(actual: pd.Series, forecast: pd.Series) -> None:
    last = pd.DatetimeIndex(actual.index)[-1].year
    for year in range(FIRST_YEAR, last + 1):
        index = hours(year)
        before = pd.date_range(index[0] - pd.Timedelta(hours=168), periods=168, freq="h")
        write(
            f"prices-{year}.json",
            {
                "year": year,
                "start": f"{year}-01-01T00:00:00Z",
                "price": values(actual, index),
                "fundamentals": values(forecast, index),
                "before": values(actual, before),
                "attribution": [EMBER_ATTRIBUTION, FORECAST_NOTE],
            },
        )


def mix_files() -> None:
    source = GenerationMixSource(DATA / "system/generation_mix.csv")
    carbon = CarbonIntensitySource(DATA / "carbon_intensity/gb_national.csv")
    for year in range(FIRST_YEAR, MIX_LAST_YEAR + 1):
        index = hours(year)
        mix = source.mix(date(year, 1, 1), date(year, 12, 31), step=pd.Timedelta(hours=1))
        mix["wind"] = mix["wind"] + mix["wind_emb"]
        intensity = carbon.intensity(
            "actual", date(year, 1, 1), date(year, 12, 31), pd.Timedelta(hours=1)
        )
        write(
            f"mix-{year}.json",
            {
                "year": year,
                "start": f"{year}-01-01T00:00:00Z",
                "mix": {fuel: values(mix[fuel], index, 0) for fuel in (*FUELS, "other")},
                "carbon": values(intensity.values, index, 0),
                "attribution": [MIX_ATTRIBUTION, CARBON_ATTRIBUTION],
            },
        )


def saturation_file() -> None:
    path = DATA / "scenarios/saturation.csv"
    if not path.is_file():
        print(f"skipped saturation.json: {path.relative_to(ROOT)} not built")
        return
    table = pd.read_csv(path)
    years = pd.read_csv(DATA / "scenarios/saturation_years.csv")
    write(
        "saturation.json",
        {
            "summary": json.loads(table.round(4).to_json(orient="records")),
            "years": json.loads(years.round(4).to_json(orient="records")),
            "source": "data/scenarios/saturation.csv (openenergy system saturation)",
        },
    )


def parity_file(actual: pd.Series) -> None:
    first, last = PARITY_MONTH
    window = gb_prices([PRICES], date(2024, 12, 1), last)[0]
    battery = BatterySpec(power_mw=1, energy_mwh=2, eta_charge=0.95, eta_discharge=0.95)
    config = BacktestConfig(dispatch=DispatchConfig(degradation_cost=5))
    days = pd.date_range(first, last).date.tolist()
    index = pd.date_range(str(first), f"{last} 23:00", freq="h", tz="UTC")
    forecasters = {
        "perfect": PerfectForesight(window),
        "naive": NaiveLastWeek(),
        "fundamentals": PrecomputedForecast(FORECAST, name="fundamentals"),
    }
    daily = {}
    plans = {}
    for name, forecaster in forecasters.items():
        run = run_backtest(battery, window, forecaster, config, days)
        daily[name] = [round(float(v), 6) for v in run.daily["revenue"]]
        plans[name] = [round(float(v), 6) for v in run.intervals["forecast"]]
    write(
        "engine-parity.json",
        {
            "battery": {
                "powerMw": 1,
                "energyMwh": 2,
                "etaCharge": 0.95,
                "etaDischarge": 0.95,
                "wear": 5,
            },
            "price": values(actual, index, 6),
            "forecast": plans,
            "revenue": daily,
        },
        ROOT / "web/src/engine",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    actual = prices()
    forecast = pd.read_csv(FORECAST, index_col="utc_timestamp")["forecast_gbp_per_mwh"]
    forecast.index = pd.DatetimeIndex(pd.to_datetime(forecast.index, utc=True))
    price_files(actual, forecast)
    mix_files()
    saturation_file()
    parity_file(actual)


if __name__ == "__main__":
    main()
