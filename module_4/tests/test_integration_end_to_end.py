"""Pull -> real DB -> refresh -> rendered values, including overlapping pulls."""
from bs4 import BeautifulSoup
from unittest.mock import Mock
import pytest
from src.app import create_app
from src.load_data import applicant_records

pytestmark = pytest.mark.integration


def test_pull_update_render(db_url, rows):
    # side_effect returns the next batch on each call. The batches overlap.
    first_batch = rows[:2]
    second_batch = rows[1:]
    pretend_scraper = Mock(side_effect=[first_batch, second_batch])
    app = create_app(
        {'TESTING': True, 'DATABASE_URL': db_url, 'PULL_SYNCHRONOUS': True},
        scraper=pretend_scraper,
    )
    client = app.test_client()
    # Pull and display the first batch: one of two entries is international.
    assert client.post('/pull-data').json == {'ok': True}
    assert len(applicant_records(db_url)) == 2
    assert client.post('/update-analysis').status_code == 200
    page = BeautifulSoup(client.get('/analysis').data, 'html.parser')
    assert '50.00%' in page.select_one('[data-question="2"]').text
    assert page.select_one('[data-question="1"] .answer').text == '2'
    # The second pull adds one entry; the repeated URL is ignored.
    assert client.post('/pull-data').status_code == 200
    assert len(applicant_records(db_url)) == 3
    assert client.post('/update-analysis').status_code == 200
    page = BeautifulSoup(client.get('/analysis').data, 'html.parser')
    assert '33.33%' in page.select_one('[data-question="2"]').text
    assert '0.00%' in page.select_one('[data-question="5"]').text
