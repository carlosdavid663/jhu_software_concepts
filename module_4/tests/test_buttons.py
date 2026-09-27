"""No sleeps: hold work in a queue to inspect the real busy state."""
from unittest.mock import Mock
import pytest
from src.app import create_app, start_worker

pytestmark = pytest.mark.buttons


def test_pull_passes_scraped_rows_to_loader(rows):
    scraper = Mock(return_value=rows)
    loader = Mock(return_value=(3, 0))
    app = create_app({"TESTING": True, "PULL_SYNCHRONOUS": True}, scraper=scraper, loader=loader)
    response = app.test_client().post("/pull-data")
    assert response.status_code == 200
    assert response.json == {'ok': True}
    scraper.assert_called_once_with()
    loader.assert_called_once_with(rows)
    assert not app.extensions["gradcafe"]["state"]["busy"]


def test_busy_gates_both_buttons_and_preserves_results(rows):
    # Keep the job in a list so we can inspect the page before it finishes.
    queued_jobs = []
    scraper = Mock(return_value=rows)
    loader = Mock(return_value=(3, 0))
    query = Mock(return_value={1: [(8,)]})
    app = create_app(
        {"TESTING": True}, scraper=scraper, loader=loader,
        query=query, runner=queued_jobs.append,
    )
    client = app.test_client()
    assert client.post("/update-analysis").json == {"ok": True}
    assert client.post("/pull-data").status_code == 202
    for route in ("/pull-data", "/update-analysis", "/pull", "/update"):
        response = client.post(route)
        assert response.status_code == 409
        assert response.json == {'busy': True}
    assert query.call_count == 1
    scraper.assert_not_called()
    loader.assert_not_called()
    page = client.get("/analysis").get_data(as_text=True)
    assert 'disabled' in page
    assert 'content="5"' in page
    assert app.extensions["gradcafe"]["state"]["results"] == {1: [(8,)]}
    # Run the saved job now. No waiting or unpredictable thread timing.
    queued_job = queued_jobs.pop()
    queued_job()
    assert not app.extensions["gradcafe"]["state"]["busy"]
    assert client.post("/update-analysis").status_code == 200


@pytest.mark.parametrize("failure", ["scraper", "loader", "runner"])
def test_failures_release_busy(failure):
    scraper = Mock(return_value=[])
    loader = Mock(return_value=(0, 0))
    runner = Mock(side_effect=RuntimeError("Worker unavailable"))
    if failure == "scraper":
        scraper.side_effect = RuntimeError("Failed")
    if failure == "loader":
        loader.side_effect = RuntimeError("Failed")
    app = create_app({"TESTING": True, "PULL_SYNCHRONOUS": failure != "runner"}, scraper=scraper, loader=loader, runner=runner)
    response = app.test_client().post("/pull-data")
    assert response.status_code == 500
    assert response.json == {'ok': False}
    assert not app.extensions["gradcafe"]["state"]["busy"]
    if failure == "scraper":
        loader.assert_not_called()


def test_update_failure_retains_last_success():
    query = Mock(side_effect=[{1: [(9,)]}, RuntimeError("DB unavailable")])
    app = create_app({"TESTING": True}, query=query)
    client = app.test_client()
    assert client.post("/update-analysis").status_code == 200
    before = app.extensions["gradcafe"]["state"].copy()
    assert client.post("/update-analysis").status_code == 500
    after = app.extensions["gradcafe"]["state"]
    assert after['results'] == before['results']
    assert after['updated'] == before['updated']


def test_thread_adapter(monkeypatch):
    thread = Mock()
    constructor = Mock(return_value=thread)
    monkeypatch.setattr("src.app.Thread", constructor)
    work = Mock()
    start_worker(work)
    constructor.assert_called_once_with(target=work, daemon=True)
    thread.start.assert_called_once_with()


def test_default_background_runner(monkeypatch):
    runner = Mock()
    monkeypatch.setattr("src.app.start_worker", runner)
    app = create_app(
        {"TESTING": True}, scraper=Mock(return_value=[]), loader=Mock(return_value=(0, 0))
    )
    assert app.test_client().post("/pull-data").status_code == 202
    saved_job = runner.call_args.args[0]
    saved_job()
    assert not app.extensions["gradcafe"]["state"]["busy"]
