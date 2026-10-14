import io
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


def test_result_page_answers_first(client: TestClient) -> None:
    page = client.get("/result", params={"year": 2024, "hours": 2, "power_mw": 10})
    assert page.status_code == 200
    text = page.text
    assert "10 MW, 2-hour battery trading GB day-ahead prices in 2024" in text
    assert "£290,000 a year</strong> (£29,000 per MW)" in text
    assert "74% of the" in text
    assert "What this assumes" in text
    assert "cdn.plot.ly" in text
    assert 'id="elapsed"' not in text  # precomputed: no waiting
    for link in ("/download/daily.csv?", "/download/scenario.yaml?", "/battery?"):
        assert link in text
    assert "power_mw=10" in text


def test_result_page_on_a_pathway_and_with_response(client: TestClient) -> None:
    pathway = client.get(
        "/result",
        params={
            "source": "scenario",
            "pathway": "Hydrogen Evolution",
            "forecast": "perfect_foresight",
        },
    ).text
    assert "would earn about" in pathway
    assert "with perfect foresight of prices, an upper bound" in pathway
    assert "not a forecast" in pathway
    naive = client.get("/result", params={"source": "scenario", "pathway": "Falling Behind"})
    assert "358 days simulated (the first week has no last week to plan on)" in naive.text
    moderation = client.get("/result", params={"year": 2022, "services": "dc_dm"}).text
    assert "281 days simulated (Dynamic Moderation starts on 26 March 2022)" in moderation
    response = client.get("/result", params={"year": 2023, "services": "dc", "hours": 1}).text
    assert "selling Dynamic Containment" in response
    assert "comes from frequency response" in response
    assert "never penalised" in response


def test_other_durations_load_while_running(client: TestClient) -> None:
    params = {"source": "scenario", "pathway": "Falling Behind", "hours": 3}
    shell = client.get("/result", params=params).text
    assert 'id="elapsed"' in shell
    assert 'data-src="/result/fragment?' in shell
    fragment = client.get("/result/fragment", params=params)
    assert fragment.status_code == 200
    assert "3-hour battery on modelled GB prices" in fragment.text
    refused = client.get("/result", params={"year": 2019, "services": "dc"})
    assert refused.status_code == 400
    assert "2022" in refused.text


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


def test_explore_shows_every_year_and_pathway(client: TestClient) -> None:
    page = client.get("/explore", params={"hours": 4, "forecast": "perfect_foresight"})
    assert page.status_code == 200
    text = page.text
    for year in range(2017, 2026):
        assert f"GB {year}</td>" in text
    assert "Ten Year Outlook" in text
    assert "plotly_click" in text  # bars open their result
    assert "/result?source=history&amp;hours=4&amp;forecast=perfect_foresight" in text
    response = client.get("/explore", params={"services": "dc_dm"}).text
    assert "GB 2022 + DC and DM</td>" in response
    assert "GB 2021" not in response
    assert "historic years only" in response
    assert client.get("/explore", params={"hours": 3}).status_code == 422


def test_compare_side_by_side_from_the_url(client: TestClient) -> None:
    params = [("item", "gb-2019"), ("item", "gb-2022"), ("item", "falling_behind_2030")]
    page = client.get("/compare", params=[*params, ("power_mw", "5")])
    assert page.status_code == 200
    text = page.text
    assert text.count('<p class="answer">') == 3
    assert "Revenue through the year" in text
    assert 'value="gb-2022" selected' in text
    empty = client.get("/compare", params=[("item", ""), ("item", "gb-2024")])
    assert empty.status_code == 200
    assert empty.text.count('<p class="answer">') == 1
    assert client.get("/compare", params={"item": "gb-1999"}).status_code == 400
    too_many = [("item", f"gb-{year}") for year in (2017, 2018, 2019, 2020)]
    assert client.get("/compare", params=too_many).status_code == 422


def test_help_next_to_inputs_and_numbers(client: TestClient) -> None:
    home = client.get("/").text
    assert home.count('class="tip"') >= 5
    assert "Revenue scales with it" in home
    for name in ("Historic year", "FES pathway", "FES year"):
        assert f'aria-label="{name}"' in home  # every select has a name
    assert "this.form.source.value='scenario'" in home
    assert '<div class="wide"><table>' in client.get("/scenarios").text
    result = client.get("/result", params={"year": 2024}).text
    assert "an upper bound" in result
    assert "/compare?hours=2&amp;forecast=naive_last_week&amp;power_mw=1&amp;item=gb-2024" in result
    assert "/explore?hours=2" in result
