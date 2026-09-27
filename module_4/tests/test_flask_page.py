"""Required routes and stable HTML components."""
from unittest.mock import Mock
import pytest
from bs4 import BeautifulSoup
from src.app import create_app

pytestmark = pytest.mark.web


def test_analysis_page():
    # Arrange: Mock is a pretend function. Here it returns one known answer.
    pretend_query = Mock(return_value={1: [(7,)]})
    website = create_app({"TESTING": True}, query=pretend_query)
    client = website.test_client()

    # Act: ask the website for the Analysis page without opening a browser.
    response = client.get("/analysis")

    # Assert: each assertion describes something that must be true.
    assert response.status_code == 200
    page = BeautifulSoup(response.data, "html.parser")
    assert "Analysis" in page.title.text
    assert "Answer:" in page.get_text()
    assert page.select_one('[data-testid="pull-data-btn"]').text == "Pull Data"
    assert page.select_one('[data-testid="update-analysis-btn"]').text == "Update Analysis"


def test_factory_routes_and_isolation():
    first = create_app({"TESTING": True}, query=Mock(return_value={}))
    second = create_app({"TESTING": True}, query=Mock(return_value={}))
    first.extensions['gradcafe']['state']['busy'] = True
    assert second.extensions['gradcafe']['state']['busy'] is False
    client = second.test_client()
    for route in ['/', '/analysis', '/static/style.css', '/static/controls.js']:
        assert client.get(route).status_code == 200
    for route in ['/pull', '/pull-data', '/update', '/update-analysis']:
        assert client.get(route).status_code == 405
    assert client.get('/missing').status_code == 404


def test_database_unavailable_is_explained():
    def fail():
        raise RuntimeError('Unavailable')
    client = create_app({'TESTING': True}, query=fail).test_client()
    response = client.get('/analysis')
    assert response.status_code == 200
    assert b'Database unavailable' in response.data
