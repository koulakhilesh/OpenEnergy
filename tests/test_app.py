from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("plotly")

from fastapi.testclient import TestClient

from openenergy import app as web

ROOT = Path(__file__).parents[1]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("OPENENERGY_DATA", str(ROOT / "data"))
    web._fes_prices.cache_clear()
    web._summary.cache_clear()
    return TestClient(web.app)


def test_health_and_pages(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"
    home = client.get("/")
    assert home.status_code == 200
    assert "Holistic Transition" in home.text
    table = client.get("/scenarios")
    assert table.status_code == 200
    assert "Ten Year Outlook" in table.text
    assert "NESO Open Data Licence" in table.text


def test_battery_on_a_fes_pathway(client: TestClient) -> None:
    page = client.get(
        "/battery",
        params={"source": "scenario", "pathway": "Falling Behind", "target": 2030},
    )
    assert page.status_code == 200, page.text
    assert "Falling Behind 2030" in page.text
    assert "Revenue per MW-year" in page.text
    assert "Future Energy Scenarios" in page.text


def test_battery_on_history_with_response(client: TestClient) -> None:
    page = client.get(
        "/battery",
        params={"year": 2024, "services": "dc", "forecast": "perfect_foresight", "hours": 1},
    )
    assert page.status_code == 200, page.text
    assert "GB 2024" in page.text
    assert "frequency response" in page.text


def test_inputs_are_bounded(client: TestClient) -> None:
    assert client.get("/battery", params={"year": 2010}).status_code == 422
    assert client.get("/battery", params={"power_mw": 0}).status_code == 422
    assert client.get("/battery", params={"hours": 24}).status_code == 422
    assert client.get("/battery", params={"source": "file"}).status_code == 422
    bad = client.get("/battery", params={"source": "scenario", "pathway": "<b>x</b>"})
    assert bad.status_code == 400
    assert "<b>x</b>" not in bad.text
    early = client.get("/battery", params={"year": 2019, "services": "dc"})
    assert early.status_code == 400
    assert "2022" in early.text
    scenario_response = client.get("/battery", params={"source": "scenario", "services": "dc"})
    assert scenario_response.status_code == 400
    assert "historic years only" in scenario_response.text


def test_run_errors_do_not_expose_details(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENENERGY_DATA", str(tmp_path))
    page = client.get("/battery", params={"year": 2024})
    assert page.status_code == 400
    assert "could not be completed" in page.text
    assert str(tmp_path) not in page.text
