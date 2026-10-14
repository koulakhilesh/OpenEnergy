"""Precompute the web app's per-MW results for common batteries.

Runs every request in ``openenergy.app.results.grid()`` (1, 2 and 4 hour batteries, both
forecasts, every historic year with and without frequency response from 2022, and every
FES pathway in 2030 and 2035) exactly as the app would run it live, and writes
data/app/summary.csv and data/app/daily.csv. Rebuild whenever the model, the app's
battery settings or the bundled data change.

Run: uv run python scripts/build_app_results.py  (about 20 minutes)
"""

import time
from pathlib import Path

from openenergy.app.results import grid, live, write

DATA = Path(__file__).parents[1] / "data"


def main() -> None:
    start = time.time()
    requests = list(grid())
    results = []
    for n, request in enumerate(requests, 1):
        results.append(live(request, DATA))
        print(f"{n}/{len(requests)} {request.key} {time.time() - start:.0f}s", flush=True)
    write(results, DATA)
    print(f"wrote {len(results)} results to {DATA / 'app'}")


if __name__ == "__main__":
    main()
