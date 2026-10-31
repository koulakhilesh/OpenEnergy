# Web app

The web app is a simulator of Britain's grid with a battery trading on it, and values a
battery on any GB day or year or on a NESO FES pathway's modelled prices. It answers in
plain sentences and keeps the charts, assumptions and sources one click away. The pages
are a React and TypeScript front end (`web/`); the year-long results come from a FastAPI
JSON API (`openenergy.app`), and the simulator, Play and 2035 run in the browser. It runs at
[open-energy-eight.vercel.app](https://open-energy-eight.vercel.app/), or locally:

```bash
uv sync                        # the app dependency group (FastAPI, plotly, uvicorn) is a default
npm --prefix web ci            # Node 22 or later
npm --prefix web run build     # writes web/dist, which the API serves
uv run uvicorn openenergy.app:app
```

Then open <http://127.0.0.1:8000/>. The app reads the repository's `data/` folder (or
`$OPENENERGY_DATA`) and the built pages from `web/dist` (or `$OPENENERGY_WEB`), so run it
from a clone; `pip install openenergy[app]` installs the API and its dependencies only. To
work on the pages, run the API as above and `npm --prefix web run dev` (Vite on port 5173,
passing API calls to port 8000).

## Pages

### In the browser

| Page | What it does |
|---|---|
| `/` | **Simulator.** Britain's grid hour by hour from 2019 to October 2026: generation by fuel flowing into the GB node, the day-ahead price, demand, carbon intensity and the wind share, with a battery charging and discharging on a plan the optimiser makes in the browser. Play at 1, 4 or 24 hours a second, step with ←/→ (shift for a day, space to play), or click a day on the year strip, coloured by each day's price spread. The side panel sets power, duration, efficiency and wear cost and the forecast the battery plans with; it shows the day's revenue for perfect foresight, OpenEnergy's forecast and last week's prices, and the whole year for all three, solved in the background a month at a time, with "best day" and "the forecast's worst miss". Notes appear on negative prices and price spikes. The address holds the day, hour and battery (`/?day=2025-01-20&hour=16&mw=1&h=2&eff=95&wear=5&plan=fundamentals`) |
| `/play` | **Play: beat the battery.** Tap or drag across the hours to plan a day from OpenEnergy's forecast; the battery (1 MW / 2 MWh, lossless, £5/MWh wear) starts and must end half full, as the optimiser's does. Run the day to see actual prices draw in and your cash against the optimiser on the same forecast and against perfect foresight; show the optimiser's plan to compare. The same day for everyone each day, and any day by link (`/play?d=2024-03-12`) |
| `/2035` | The [storage saturation study](forward-scenarios.md#how-much-storage-can-gb-use): pick a pathway and slide the battery fleet to see what one more battery earns, how hard the fleet works and how much firm capacity is still needed (`/2035?pathway=Falling+Behind&fleet=2`) |
| `/research` | The pages below, for whole years, pathways and downloads |
| `/embed/arbitrage` | Draggable prices with the optimal plan, for the docs ([Concepts](../concepts.md)) |

`?embed=1` shows the simulator or 2035 without the header, for embedding (as on
[Findings](../findings.md)). The 6.0 addresses `/lab` and `/replay` open the simulator with
their day and battery.

Revenue in these pages is after wear: what the plan earns at actual prices less the wear
cost on every MWh moved, the quantity the optimiser maximises, so no plan beats perfect
foresight. (The year results from the API below report revenue before wear, as the Python
backtest does.)

These pages read static files (`web/public/data/`, written by
`scripts/build_app_data.py` and served at `/data/<file>`): hourly prices and the fundamentals forecast for each year,
the generation mix and carbon intensity, and the saturation study, each with its
attribution. The optimiser is the same daily mixed-integer programme as
`openenergy.dispatch.optimise_dispatch`, built in TypeScript (`web/src/engine/`) and
solved by [HiGHS compiled to WebAssembly](https://github.com/lovasoa/highs-js) (MIT,
about 3.5 MB, loaded on first use). `npm test` checks it against the Python backtest on a
month of 2025 for all three forecasts, day by day (`engine-parity.json`).

### From the API

| Page | What it does |
|---|---|
| `/run` | Form: historic GB year (2017–2025, Ember prices) or a FES pathway in 2030 or 2035; power (MW) and duration (0.5–8 hours); forecast (last week's prices, OpenEnergy's forecast from 2019, or perfect foresight); frequency response (none, Dynamic Containment, or Containment and Moderation; historic years from 2022) |
| `/result` | The answer: one sentence (revenue for your MW, share of perfect foresight, cycles a day), key numbers, cumulative and monthly revenue charts, what the result assumes, sources, and links to download it. At once for 1, 2 and 4 hour batteries; otherwise a progress counter while it runs |
| `/explore` | Battery value by GB year (2017–2025) and by FES pathway (2030, 2035) for one duration, forecast and response option, as bar charts and tables; click a bar to open its result |
| `/compare` | Up to three results side by side (table, revenue through the year, and each answer); the page address holds the comparison, so it can be shared, e.g. `/compare?item=gb-2019&item=gb-2022&item=falling_behind_2030` |
| `/scenarios` | Each FES pathway's modelled results on 2025's weather next to NESO's own figures |
| `/download/daily.csv` | Daily revenue and perfect-foresight revenue for your MW, with the data credit on the first line |
| `/download/scenario.yaml` | The scenario that reproduces the result with `openenergy run` (or `openenergy system run` for a FES pathway) from the repository folder |
| `/battery` | The full hourly report of `openenergy report` (runs the backtest now) |
| `/health` | Status and version |

Page addresses and their query parameters are the same as before v5.0 (the form moved from
`/` to `/run` in v6.0), so shared results keep working. Every input and key number has a
"?" next to it that explains it in a sentence (hover, tab to it, or tap). The battery uses
95% efficiency each way and a £5/MWh wear cost. Light and dark themes follow the system
setting, and the button in the header switches them.
On Vercel a run took 18 seconds for GB 2024, 14 seconds for a FES pathway and 44 seconds
with Dynamic Containment (measured 14 October 2026). Pathway prices are precomputed in
`data/scenarios/` by `scripts/build_scenario_prices.py` (see
[Forward scenarios](forward-scenarios.md)), so the app does not need PyPSA. Inputs are
bounded query parameters, and error messages are fixed texts, never exception details.

## JSON API

The front end uses only this API, so anything it shows can be fetched directly:

| Endpoint | Returns |
|---|---|
| `/api/options` | Years, pathways, limits, forecast and service names, and the "?" explanations |
| `/api/result` | One battery: request, per-MW summary, daily revenue, and the answer, assumptions and sources for `power_mw` |
| `/api/explore` | Per-MW summaries by GB year (for `services`) and by FES pathway, for `hours` 1, 2 or 4 and `forecast` |
| `/api/compare` | Up to three results named by `item` (e.g. `gb-2022-dc`, `falling_behind_2030`), and every option |
| `/api/scenarios` | The FES pathway table with its note and attribution |

`/api/result` takes `source`, `year` (history), `pathway` and `target` (scenario), `hours`,
`forecast`, `services` and `power_mw`. Results are per MW, because revenue scales with power
at a fixed duration:

```json
{
  "key": "gb-2024-2h-naive_last_week-none",
  "label": "2 h battery, GB 2024",
  "precomputed": true,
  "request": {"source": "history", "year": 2024, "hours": 2.0, "prices": "gb-2024", "...": "..."},
  "summary": {"days": 366, "revenue_per_mw_year": 29048.5, "perfect_per_mw_year": 39304.0,
              "capture_ratio": 0.739, "cycles_per_day": 1.57, "captured_spread": 26.73,
              "forecast_mae": 19.54, "response_share": 0.0},
  "daily": {"date": ["2024-01-01", "..."], "revenue": [111.27, "..."],
            "benchmark_revenue": [241.64, "..."]},
  "text": {"power_mw": 1.0, "answer": "A 1 MW, 2-hour battery trading ...",
           "assumptions": ["..."], "sources": "..."}
}
```

1, 2 and 4 hour batteries on every year, forecast, response option and FES pathway are
precomputed in `data/app/` by `scripts/build_app_results.py` and return at once; other
durations run live. A request that cannot run (for example frequency response before
2022) returns status 400 with an `error` message.

The front end's TypeScript types are generated from the API's OpenAPI schema:
`uv run python scripts/export_openapi.py` writes `web/src/api/openapi.json`, and
`npm --prefix web run api-types` turns it into `web/src/api/schema.d.ts`. CI fails if either
is out of date.

## Tests

`uv run pytest tests/test_app.py` checks the API; in `web/`, `npm test` runs the unit tests
(Vitest) and `npm run e2e` runs the pages in Chromium against the real API (Playwright, after
`npm run build`).

## Vercel

The repository deploys to [Vercel](https://vercel.com/docs/frameworks/backend/fastapi) as
one Python function. `vercel.json` builds the front end first (`npm --prefix web ci && npm
--prefix web run build`); `app.py` at the root imports `openenergy.app:app`, which serves
the API and the built pages. Vercel installs the project with uv, including the `app`
dependency group (default groups other than `dev`); `vercel.json` gives the function up to
120 seconds and leaves out tests, docs, scripts, the front end's sources and data files the
app does not read.
