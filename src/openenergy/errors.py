"""Exceptions raised by OpenEnergy."""


class OpenEnergyError(Exception):
    """Base class for all OpenEnergy errors."""


class ConfigError(OpenEnergyError):
    """A scenario or component is configured with invalid values."""


class DataError(OpenEnergyError):
    """Input data is missing, malformed or inconsistent."""


class DispatchError(OpenEnergyError):
    """A dispatch plan cannot be produced or applied."""


class InfeasibleDispatchError(DispatchError):
    """The dispatch optimisation has no feasible solution."""
