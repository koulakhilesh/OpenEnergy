from pathlib import Path

import pytest

from openenergy.scenario import load_scenario

EXAMPLES = sorted((Path(__file__).parents[1] / "examples").glob("*.yaml"))


def test_examples_exist() -> None:
    assert len(EXAMPLES) >= 3


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_scenario_is_valid(path: Path) -> None:
    scenario = load_scenario(path)
    assert scenario.name == path.stem
    assert scenario.data.path.is_file()
