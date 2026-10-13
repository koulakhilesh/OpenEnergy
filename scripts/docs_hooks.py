"""MkDocs hook: build an example report from the bundled data before the docs build.

The report goes to docs/reports/example.html (gitignored) and is published with the site.
It is built once; delete the file to rebuild it.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from openenergy.report import build_report, load_output
from openenergy.scenario import load_scenario, run_scenario, write_outputs
from openenergy.system.scenario import (
    load_system_scenario,
    run_system_scenario,
    write_system_outputs,
)

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "docs" / "reports" / "example.html"
log = logging.getLogger("mkdocs.hooks.report")


def on_pre_build(config: Any) -> None:
    if TARGET.is_file():
        return
    log.info("building the example report into %s", TARGET.relative_to(ROOT))
    with tempfile.TemporaryDirectory() as work:
        battery = write_outputs(
            run_scenario(load_scenario(ROOT / "examples/gb-2019-naive.yaml")),
            Path(work) / "battery",
        )
        system = write_system_outputs(
            run_system_scenario(load_system_scenario(ROOT / "examples/gb-2019-system.yaml")),
            Path(work) / "system",
        )
        page = build_report(
            [load_output(battery), load_output(system)],
            title="OpenEnergy example report: GB 2019",
            cdn=True,
        )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(page, encoding="utf-8")
