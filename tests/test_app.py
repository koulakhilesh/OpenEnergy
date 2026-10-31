import importlib.util
import io
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

pytest.importorskip("fastapi")
pytest.importorskip("plotly")

from fastapi.testclient import TestClient

from openenergy.app import app
from openenergy.app import results as app_results
from openenergy.app.runs import Request, from_prices
from openenergy.scenario import Scenario
from openenergy.system.scenario import SystemScenario

ROOT = Path(__file__).parents[1]
DATA = ROOT / "data"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("OPENENERGY_DATA", str(DATA))
    monkeypatch.setenv("OPENENERGY_WEB", str(tmp_path / "web"))
    return TestClient(app)


def test_health_and_options(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"
    options = client.get("/api/options").json()
    assert options["history_years"] == list(range(2017, 2026))
    assert options["response_from"] == 2022
    assert "Ten Year Outlook" in options["pathways"]
    assert options["scenario_years"] == [2030, 2035]
    assert options["precomputed_hours"] == [1.0, 2.0, 4.0]
    assert options["hours_range"] == [0.5, 8.0]
    assert "Revenue scales with it" in options["help"]["power"]
    assert options["services"]["dc"] == "Dynamic Containment"


def test_scenarios_table(client: TestClient) -> None:
    body = client.get("/api/scenarios").json()
    assert len(body["rows"]) == 12
    first = body["rows"][0]
    assert first["pathway"] == "Holistic Transition" and first["year"] == 2030
    assert "NESO Open Data Licence" in body["attribution"]
    assert "not a forecast" in body["note"]


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
    assert client.get("/api/result", params={"power_mw": 5000}).status_code == 422


def test_run_errors_do_not_expose_details(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENENERGY_DATA", str(tmp_path))
    page = client.get("/battery", params={"year": 2024})
    assert page.status_code == 400
    assert "could not be completed" in page.text
    assert str(tmp_path) not in page.text
    api = client.get("/api/result", params={"year": 2024, "hours": 3})
    assert api.status_code == 400
    assert str(tmp_path) not in api.text


def test_api_serves_precomputed_results(client: TestClient) -> None:
    body = client.get("/api/result", params={"year": 2024, "hours": 2, "power_mw": 10}).json()
    assert body["precomputed"] is True
    assert body["key"] == "gb-2024-2h-naive_last_week-none"
    assert body["label"] == "2 h battery, GB 2024"
    assert body["request"]["prices"] == "gb-2024" and body["request"]["where"] == "GB 2024"
    summary = body["summary"]
    assert summary["days"] == len(body["daily"]["date"]) == 366
    assert 0 < summary["revenue_per_mw_year"] < summary["perfect_per_mw_year"]
    answer = body["text"]["answer"]
    assert "10 MW, 2-hour battery trading GB day-ahead prices in 2024" in answer
    assert "£290,000 a year (£29,000 per MW)" in answer
    assert "74% of the" in answer
    assert any("price taker" in item for item in body["text"]["assumptions"])
    assert "Ember" in body["text"]["sources"]


def test_answers_on_a_pathway_and_with_response(client: TestClient) -> None:
    def text(**params: object) -> dict[str, object]:
        return client.get("/api/result", params=params).json()["text"]

    pathway = text(source="scenario", pathway="Hydrogen Evolution", forecast="perfect_foresight")
    assert "would earn about" in str(pathway["answer"])
    assert "with perfect foresight of prices, an upper bound" in str(pathway["answer"])
    assert any("not a forecast" in item for item in pathway["assumptions"])  # type: ignore[attr-defined]
    naive = text(source="scenario", pathway="Falling Behind")
    assert "358 days simulated (the first week has no last week to plan on)" in str(
        naive["assumptions"]
    )
    moderation = text(year=2022, services="dc_dm")
    assert "281 days simulated (Dynamic Moderation starts on 26 March 2022)" in str(
        moderation["assumptions"]
    )
    response = text(year=2023, services="dc", hours=1)
    assert "selling Dynamic Containment" in str(response["answer"])
    assert "comes from frequency response" in str(response["answer"])
    assert "never penalised" in str(response["assumptions"])


def test_precomputed_equals_a_live_run() -> None:
    request = Request("scenario", 2030, 2.0, pathway="Falling Behind")
    store = app_results.store(DATA)
    assert store is not None
    stored = store.get(request)
    assert stored is not None
    fresh = app_results.live(request, DATA)
    # Tied modelled prices let the solver pick another equal-cost plan per platform (0.1% on Linux).
    for name, value in fresh.summary.items():
        assert stored.summary[name] == pytest.approx(value, rel=5e-3, abs=1e-9), name
    assert list(stored.daily.index) == list(fresh.daily.index)
    assert stored.daily.sum().to_numpy() == pytest.approx(fresh.daily.sum().to_numpy(), rel=5e-3)


def test_api_runs_other_durations_live(client: TestClient) -> None:
    body = client.get(
        "/api/result", params={"source": "scenario", "pathway": "Falling Behind", "hours": 3}
    ).json()
    assert body["precomputed"] is False
    assert body["label"] == "3 h battery, Falling Behind 2030"
    assert "3-hour battery on modelled GB prices" in body["text"]["answer"]


def test_api_rejects_requests_that_cannot_run(client: TestClient) -> None:
    response = client.get("/api/result", params={"year": 2019, "services": "dc"})
    assert response.status_code == 400
    assert "2022" in response.json()["error"]
    assert client.get("/api/result", params={"hours": 9}).status_code == 422


def test_grid_covers_every_option_once() -> None:
    keys = [request.key for request in app_results.grid()]
    assert len(keys) == len(set(keys)) == 219
    assert not any("fundamentals" in key for key in keys if not key.startswith("gb-"))
    assert app_results.store(Path("/nonexistent")) is None


def test_downloads_reproduce_the_result(client: TestClient) -> None:
    csv = client.get("/download/daily.csv", params={"year": 2024, "power_mw": 10})
    assert csv.status_code == 200
    assert "attachment" in csv.headers["content-disposition"]
    frame = pd.read_csv(io.StringIO(csv.text), comment="#")
    assert list(frame.columns) == ["date", "revenue_gbp", "perfect_foresight_revenue_gbp"]
    assert len(frame) == 366
    assert frame["revenue_gbp"].sum() * 365 / 366 == pytest.approx(290_392, rel=1e-3)

    history = client.get("/download/scenario.yaml", params={"year": 2023, "services": "dc"})
    scenario = Scenario.model_validate(yaml.safe_load(history.text), context={"base": ROOT})
    assert scenario.data.path.is_file()
    assert scenario.response is not None and scenario.response.services == ["DCL", "DCH"]
    forward = client.get(
        "/download/scenario.yaml", params={"source": "scenario", "pathway": "Falling Behind"}
    )
    system = SystemScenario.model_validate(yaml.safe_load(forward.text), context={"base": ROOT})
    assert system.system.fes is not None and system.system.fes.pathway == "Falling Behind"


def test_prices_tokens_round_trip() -> None:
    for request in app_results.grid():
        assert from_prices(request.prices, request.hours, request.forecast) == request
    assert from_prices("gb-2019-dc", 2.0, "naive_last_week") is None  # response from 2022
    assert from_prices("gb-1999", 2.0, "naive_last_week") is None
    assert from_prices("<script>", 2.0, "naive_last_week") is None


def test_explore_lists_every_year_and_pathway(client: TestClient) -> None:
    body = client.get("/api/explore", params={"hours": 4, "forecast": "perfect_foresight"}).json()
    assert [x["request"]["where"] for x in body["history"]] == [
        f"GB {year}" for year in range(2017, 2026)
    ]
    assert len(body["pathways"]) == 12
    assert body["history"][0]["request"]["hours"] == 4
    response = client.get("/api/explore", params={"services": "dc_dm"}).json()
    assert response["history"][0]["request"]["where"] == "GB 2022 + DC and DM"
    assert len(response["history"]) == 4
    assert client.get("/api/explore", params={"hours": 3}).status_code == 422


def test_compare_from_prices_tokens(client: TestClient) -> None:
    params = [("item", "gb-2019"), ("item", "gb-2022"), ("item", "falling_behind_2030")]
    body = client.get("/api/compare", params=[*params, ("power_mw", "5")]).json()
    assert [x["request"]["prices"] for x in body["results"]] == [
        "gb-2019",
        "gb-2022",
        "falling_behind_2030",
    ]
    assert all("A 5 MW" in x["text"]["answer"] for x in body["results"])
    assert len(body["options"]) == 29  # 9 years, 2022-2025 with DC and DC+DM, 12 pathways
    empty = client.get("/api/compare", params=[("item", ""), ("item", "gb-2024")]).json()
    assert len(empty["results"]) == 1
    assert client.get("/api/compare", params={"item": "gb-1999"}).status_code == 400
    too_many = [("item", f"gb-{year}") for year in (2017, 2018, 2019, 2020)]
    assert client.get("/api/compare", params=too_many).status_code == 422


def test_front_end_routes_serve_the_built_page(client: TestClient, tmp_path: Path) -> None:
    missing = client.get("/explore")
    assert missing.status_code == 503
    assert "npm --prefix web run build" in missing.text
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<div id='root'></div>")
    (web / "assets/app-1.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("no")
    for path in ("/", "/result?year=2024", "/explore", "/compare?item=gb-2019", "/scenarios"):
        page = client.get(path)
        assert page.status_code == 200 and "root" in page.text, path
    asset = client.get("/assets/app-1.js")
    assert asset.status_code == 200 and "immutable" in asset.headers["cache-control"]
    assert client.get("/assets/../../secret.txt").status_code == 404
    assert client.get("/assets/%2e%2e/%2e%2e/secret.txt").status_code == 404
    assert client.get("/assets/missing.js").status_code == 404


def test_openapi_schema_is_current() -> None:
    spec = importlib.util.spec_from_file_location("export", ROOT / "scripts/export_openapi.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = (ROOT / "web/src/api/openapi.json").read_text()
    assert json.loads(committed) == json.loads(module.schema()), (
        "run: uv run python scripts/export_openapi.py && npm --prefix web run api-types"
    )
