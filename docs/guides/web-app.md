# Web app

`openenergy.app` is a small FastAPI app on the Python API. It values a battery on a
historic GB year or on a NESO FES pathway's modelled prices and shows the same interactive
report as `openenergy report`. It runs at
[open-energy-eight.vercel.app](https://open-energy-eight.vercel.app/), or locally:

```bash
uv sync                        # the app dependency group (FastAPI, plotly, uvicorn) is a default
uv run uvicorn openenergy.app:app
```

Then open <http://127.0.0.1:8000/>.

| Page | What it does |
|---|---|
| `/` | Form: historic GB year (2017–2025, Ember prices) or a FES pathway in 2030 or 2035; power (MW) and duration (0.5–8 hours); forecast (last week's prices or perfect foresight); frequency response (none, Dynamic Containment, or Containment and Moderation; historic years from 2022) |
| `/battery` | Runs the backtest and its perfect-foresight benchmark and returns the HTML report (plotly from its CDN) |
| `/scenarios` | Each FES pathway's modelled results on 2025's weather next to NESO's own figures |
| `/api/result` | JSON: per-MW summary and daily revenue for the same request (without `power_mw`); see below |
| `/health` | Status and version |

The battery uses 95% efficiency each way and a £5/MWh wear cost. On Vercel a run took
18 seconds for GB 2024, 14 seconds for a FES pathway and 44 seconds with Dynamic
Containment (measured 14 October 2026). Pathway prices are precomputed in `data/scenarios/` by
`scripts/build_scenario_prices.py` (see [Forward scenarios](forward-scenarios.md)), so the
app does not need PyPSA. Inputs are bounded query parameters; the app reads only the
bundled data, from `$OPENENERGY_DATA` or `./data`.

## JSON API

`/api/result` takes the same parameters as `/battery` (`source`, `year`, `pathway`,
`target`, `hours`, `forecast`, `services`) and returns results per MW, because revenue
scales with power at a fixed duration:

```json
{
  "key": "gb-2024-2h-naive_last_week-none",
  "label": "2 h battery, GB 2024",
  "precomputed": true,
  "summary": {"days": 366, "revenue_per_mw_year": 29039.2, "perfect_per_mw_year": 39304.0,
              "capture_ratio": 0.739, "cycles_per_day": 1.57, "captured_spread": 26.72,
              "forecast_mae": 19.54, "response_share": 0.0},
  "daily": {"date": ["2024-01-01", "..."], "revenue": [111.27, "..."],
            "benchmark_revenue": [241.64, "..."]}
}
```

1, 2 and 4 hour batteries on every year, forecast, response option and FES pathway are
precomputed in `data/app/` by `scripts/build_app_results.py` and return at once; other
durations run live. A request that cannot run (for example frequency response before
2022) returns status 400 with an `error` message.

## Vercel

The repository deploys to [Vercel](https://vercel.com/docs/frameworks/backend/fastapi) as
one Python function. `app.py` at the root imports `openenergy.app:app`; Vercel installs the
project with uv, including the `app` dependency group (default groups other than `dev`);
`vercel.json` gives the function up to 120 seconds and leaves out tests, docs, scripts and
data files the app does not read.
