import re

import pytest

import openenergy
from openenergy import (
    ConfigError,
    DataError,
    DispatchError,
    InfeasibleDispatchError,
    OpenEnergyError,
)


def test_version_is_pep440() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+((a|b|rc)\d+)?(\.dev\d+)?", openenergy.__version__)


@pytest.mark.parametrize("error", [ConfigError, DataError, DispatchError])
def test_errors_share_base(error: type[OpenEnergyError]) -> None:
    assert issubclass(error, OpenEnergyError)


def test_infeasible_is_dispatch_error() -> None:
    with pytest.raises(DispatchError):
        raise InfeasibleDispatchError("no feasible plan")
