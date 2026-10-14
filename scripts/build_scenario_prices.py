"""Precompute hourly GB prices for each NESO FES pathway, for the web app and the docs.

Each pathway's 2030 and 2035 system is solved on 2025's weather with price-taking
interconnector links at the availability fitted from their flows and unit commitment
(``system.fes``, ``interconnectors: links``, ``commitment: true``, marginal price, other
assumptions default), exactly as ``openenergy system run`` would. Writes:

- data/scenarios/fes_prices.csv: hourly modelled price (GBP/MWh) per pathway and year
- data/scenarios/fes_summary.csv: one row per run with the model's results next to FES's
  own interconnector imports, exports and curtailment for the same year

Sources: NESO Future Energy Scenarios 2025 and Ten Year Outlook 2026 (ES1, ED1), NESO
historic generation mix and Interconnector Register (NESO Open Data Licence v1.0, supported
by National Energy SO Open Data); DUKES, QEP and carbon prices as in data/system; Ember
neighbour prices (CC BY 4.0) at ECB rates; Elexon BMRS FUELHH (contains BMRS data © Elexon
Limited copyright and database right 2026).

Run: uv run python scripts/build_scenario_prices.py  (needs the system extra)
"""

from pathlib import Path

import pandas as pd

from openenergy.data.fes import PATHWAYS, FesSource
from openenergy.system.forward import price_column
from openenergy.system.scenario import SystemScenario, run_system_scenario

ROOT = Path(__file__).parents[1]
DATA = ROOT / "data"
OUT = DATA / "scenarios"
WEATHER_YEAR = 2025
YEARS = (2030, 2035)


def main() -> None:
    fes = FesSource(DATA / "fes")
    prices = {}
    rows = []
    for pathway in PATHWAYS:
        for year in YEARS:
            system = {
                "data": str(DATA / "system"),
                "year": WEATHER_YEAR,
                "interconnectors": "links",
                "commitment": True,
                "fes": {"pathway": pathway, "year": year},
            }
            run = run_system_scenario(
                SystemScenario.model_validate({"name": "fes", "system": system})
            )
            s = run.summary
            prices[price_column(pathway, year)] = run.result.price.round(2)
            curtailed = fes.supply(pathway, year, "Curtailment (TWh)").sum()
            rows.append(
                {
                    "pathway": pathway,
                    "year": year,
                    "weather_year": WEATHER_YEAR,
                    "price_mean": round(s.price_mean, 1),
                    "daily_spread": round(s.daily_spread, 1),
                    "imports_twh": round(s.imports_twh or 0.0, 1),
                    "exports_twh": round(s.exports_twh or 0.0, 1),
                    "curtailment_twh": round(s.curtailment_twh, 1),
                    "unserved_gwh": round(s.unserved_mwh / 1000, 1),
                    "emissions_mt": round(s.emissions_mt, 1),
                    "fes_imports_twh": round(
                        fes.supply(pathway, year, "Import (TWh)").get("Interconnectors", 0.0), 1
                    ),
                    "fes_exports_twh": round(
                        -fes.supply(pathway, year, "Export (TWh)").get("Interconnectors", 0.0), 1
                    ),
                    "fes_curtailment_twh": round(curtailed, 1),
                }
            )
            print(rows[-1], flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(prices)
    frame.index = frame.index.strftime("%Y-%m-%dT%H:%M:%SZ")
    frame.to_csv(OUT / "fes_prices.csv", index_label="utc_timestamp")
    pd.DataFrame(rows).to_csv(OUT / "fes_summary.csv", index=False)
    print(f"wrote {OUT / 'fes_prices.csv'} and {OUT / 'fes_summary.csv'}")


if __name__ == "__main__":
    main()
