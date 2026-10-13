# Reports

`openenergy report` turns saved outputs into one HTML file of charts and tables. It reads
what the other commands wrote, so nothing is re-run and any past run can be reported.

```bash
uv sync --extra report      # or: pip install 'openenergy[report]'  (plotly)
uv run openenergy run examples/gb-2019-naive.yaml --out outputs/naive
uv run openenergy run examples/gb-2019-perfect.yaml --out outputs/perfect
uv run openenergy report outputs/naive outputs/perfect -o outputs/report.html
```

See the [example report](../reports/example.html) for GB 2019 (a battery on real prices and
the system model), built from the bundled data when these docs are built.

## What goes in

| Input | Written by | Sections |
|---|---|---|
| A run directory | `openenergy run` | Key figures; cumulative revenue against perfect foresight; revenue by month; average day; stored energy by day and hour; price and forecast; forecast error by hour; plant output and emissions where the run has them |
| A system directory | `openenergy system run` | Key figures; generation by month; price duration curve; mean price by hour; curtailment and emissions by month; battery figures when present |
| A backcast directory | `openenergy system validate --out` | The per-year table; model and actual price by hour and by month; duration curves; gas and coal by year |
| A sweep CSV | `openenergy sweep --out` | Results table; ranking; revenue per MW-year against each swept setting |

The kind is detected from the files. Several run directories also get a comparison section
(key figures side by side and cumulative revenue on one chart), as do several system
directories (duration curves and price by hour together).

## Options

| Option | Default | Meaning |
|---|---|---|
| `-o`, `--out` | `report.html` | File to write |
| `--title` | `OpenEnergy report` | Title at the top of the page |
| `--cdn` | off | Load plotly.js from its CDN: about 0.4 MB per chart instead of a 5 MB self-contained file, but the report then needs internet to show charts |

By default the report is self-contained and opens offline. Charts are interactive: zoom,
pan, hide a series by clicking its legend entry, or save a chart as PNG from its toolbar.

## Numbers and sources

Key figures come from each run's `summary.json` exactly as written, so they match what the
command printed. Each section repeats the run's notes and data attribution, and the footer
states the licences; share the report with those intact. `openenergy run` also writes
`benchmark_daily.csv`, the perfect-foresight benchmark by day, which the revenue chart uses.

## In Python

The charts are plain functions from pandas to plotly figures, so they work in notebooks and
apps too:

```python
from openenergy.report import build_report, load_output
from openenergy.report import figures

run = load_output("outputs/naive")
figures.state_of_charge(run.intervals).show()
html = build_report([run], title="Naive 2019")
```
