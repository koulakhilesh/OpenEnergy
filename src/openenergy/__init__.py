"""Backtest battery storage and renewables against real power-market data."""

from openenergy.errors import (
    ConfigError,
    DataError,
    DispatchError,
    InfeasibleDispatchError,
    OpenEnergyError,
)

__version__ = "3.3.0"

__all__ = [
    "ConfigError",
    "DataError",
    "DispatchError",
    "InfeasibleDispatchError",
    "OpenEnergyError",
    "__version__",
]
