from pathlib import Path

import pytest

from openenergy.scenario import load_scenario
from openenergy.system.scenario import is_system_scenario, load_system_scenario

EXAMPLES = sorted((Path(__file__).parents[1] / "examples").glob("*.yaml"))


def test_examples_exist() -> None:
    assert len(EXAMPLES) >= 3


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_scenario_is_valid(path: Path) -> None:
    if is_system_scenario(path):
        system = load_system_scenario(path)
        assert system.name == path.stem
        assert (system.system.data / "generation_mix.csv").is_file()
        return
    scenario = load_scenario(path)
    assert scenario.name == path.stem
    assert scenario.data.path.is_file()
