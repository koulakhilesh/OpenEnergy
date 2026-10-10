"""System-level analysis: net load, surplus, storage needs and GB dispatch."""

from openenergy.system.fleet import (
    Adjustments,
    FleetAssumptions,
    build_system,
    thermal_generators,
)
from openenergy.system.merit import merit_order
from openenergy.system.model import Generator, Storage, SystemResult, SystemSpec, solve
from openenergy.system.netload import (
    NetLoadStats,
    SystemData,
    duration_curve,
    load_system,
    net_load,
    netload_by_year,
    surplus,
)
from openenergy.system.storage import FleetResult, absorb_surplus, sizing_grid
from openenergy.system.validate import Backcast, BackcastYear, backcast, write_backcast

__all__ = [
    "Adjustments",
    "Backcast",
    "BackcastYear",
    "FleetAssumptions",
    "FleetResult",
    "Generator",
    "NetLoadStats",
    "Storage",
    "SystemData",
    "SystemResult",
    "SystemSpec",
    "absorb_surplus",
    "backcast",
    "build_system",
    "duration_curve",
    "load_system",
    "merit_order",
    "net_load",
    "netload_by_year",
    "sizing_grid",
    "solve",
    "surplus",
    "thermal_generators",
    "write_backcast",
]
