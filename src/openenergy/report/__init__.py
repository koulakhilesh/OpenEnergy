"""HTML reports from OpenEnergy outputs (needs the ``report`` extra: plotly)."""

from openenergy.report.document import build_report
from openenergy.report.load import (
    BackcastOutput,
    BatteryOutput,
    Output,
    SweepOutput,
    SystemOutput,
    load_output,
)

__all__ = [
    "BackcastOutput",
    "BatteryOutput",
    "Output",
    "SweepOutput",
    "SystemOutput",
    "build_report",
    "load_output",
]
