# Web app

`openenergy.app` is a small FastAPI app on the Python API. It values a battery on a
historic GB year or on a NESO FES pathway's modelled prices and shows the same interactive
report as `openenergy report`.

```bash
uv sync                        # the app dependency group (FastAPI, plotly, uvicorn) is a default
uv run uvicorn openenergy.app:app
```

Then open <http://127.0.0.1:8000/>.

| Page | What it does |
|---|---|
| `/` | Form: historic GB year (2017\u20132025, Ember prices) or a FES pathway in 2030 or 2035; power (MW) and duration (0.5\u20138 hours); forecast (last week's prices or perfect foresight); frequency response (none, Dynamic Containment, or Containment and Moderation; historic years from 2022) |
| `/battery` | Runs the backtest and its perfect-foresight benchmark and returns the HTML report (plotly from its CDN) |
| `/scenarios` | Each FES pathway's modelled results on 2025's weather next to NESO's own figures |
| `/health` | Status and version |

The battery uses 95% efficiency each way and a \u00a35/MWh wear cost; each run takes about
10 to 30 seconds. Pathway prices are precomputed in `data/scenarios/` by
`scripts/build_scenario_prices.py` (see [Forward scenarios](forward-scenarios.md)), so the
app does not need PyPSA. Inputs are bounded query parameters; the app reads only the
bundled data, from `$OPENENERGY_DATA` or `./data`.

## Vercel

The repository deploys to [Vercel](https://vercel.com/docs/frameworks/backend/fastapi) as
one Python function. `app.py` at the root imports `openenergy.app:app`; Vercel installs the
project with uv, including the `app` dependency group (default groups other than `dev`);
`vercel.json` gives the function up to 120 seconds and leaves out tests, docs, scripts and
data files the app does not read.
