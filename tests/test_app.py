from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("plotly")

from fastapi.testclient import TestClient

from openenergy.app import app
from openenergy.app import results as app_results
from openenergy.app.runs import Request

ROOT = Path(__file__).parents[1]
DATA = ROOT / "data"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("OPENENERGY_DATA", str(DATA))
    return TestClient(app)


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


def test_api_serves_precomputed_results(client: TestClient) -> None:
    body = client.get("/api/result", params={"year": 2024, "hours": 2}).json()
    assert body["precomputed"] is True
    assert body["key"] == "gb-2024-2h-naive_last_week-none"
    assert body["label"] == "2 h battery, GB 2024"
    summary = body["summary"]
    assert summary["days"] == len(body["daily"]["date"]) == 366
    assert 0 < summary["revenue_per_mw_year"] < summary["perfect_per_mw_year"]


def test_precomputed_equals_a_live_run() -> None:
    request = Request("scenario", 2030, 2.0, pathway="Falling Behind")
    store = app_results.store(DATA)
    assert store is not None
    stored = store.get(request)
    assert stored is not None
    fresh = app_results.live(request, DATA)
    for name, value in fresh.summary.items():
        assert stored.summary[name] == pytest.approx(value, rel=1e-5, abs=1e-9), name
    assert (stored.daily - fresh.daily).abs().max().max() < 0.01
    assert list(stored.daily.index) == list(fresh.daily.index)


def test_api_runs_other_durations_live(client: TestClient) -> None:
    body = client.get(
        "/api/result", params={"source": "scenario", "pathway": "Falling Behind", "hours": 3}
    ).json()
    assert body["precomputed"] is False
    assert body["label"] == "3 h battery, Falling Behind 2030"


def test_api_rejects_requests_that_cannot_run(client: TestClient) -> None:
    response = client.get("/api/result", params={"year": 2019, "services": "dc"})
    assert response.status_code == 400
    assert "2022" in response.json()["error"]
    assert client.get("/api/result", params={"hours": 9}).status_code == 422


def test_grid_covers_every_option_once() -> None:
    keys = [request.key for request in app_results.grid()]
    assert len(keys) == len(set(keys)) == 174
    assert app_results.store(Path("/nonexistent")) is None
