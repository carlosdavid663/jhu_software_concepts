"""Incremental collection, LLM fallback, and the app's default pipeline."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from src import pull_data
from src.app import create_app
from src.clean import load_data
from src.load_data import applicant_records, insert_applicants

pytestmark = pytest.mark.integration


def configure_scrape(monkeypatch, pages, next_url=None):
    monkeypatch.setattr(pull_data, 'check_robots', lambda **kw: (SimpleNamespace(can_fetch=lambda *a: True), 2))
    monkeypatch.setattr(pull_data.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(pull_data, '_download', lambda url: 'saved HTML')
    monkeypatch.setattr(pull_data, 'parse_page', Mock(side_effect=pages))
    monkeypatch.setattr(pull_data, 'next_page_url', lambda *a: next_url)


def test_incremental_stops_at_existing_page(monkeypatch, tmp_path):
    configure_scrape(monkeypatch, [[{'url':'new'}, {'url':'new'}, {}], [{'url':'old'}]], pull_data.BASE_URL + 'survey/?page=2')
    report = Mock()
    assert pull_data.scrape_new_data({'old'}, report, tmp_path) == [{'url':'new'}]
    assert report.call_count == 2
    configure_scrape(monkeypatch, [[]])
    assert pull_data.scrape_new_data(set(), data_dir=tmp_path) == []


def test_incremental_repeated_or_forbidden_page(monkeypatch, tmp_path):
    configure_scrape(monkeypatch, [[{'url':'new'}]], pull_data.BASE_URL + 'survey/')
    with pytest.raises(ValueError, match='repeated a page'):
        pull_data.scrape_new_data(set(), data_dir=tmp_path)
    monkeypatch.setattr(pull_data, 'check_robots', lambda **kw: (SimpleNamespace(can_fetch=lambda *a: False), 2))
    with pytest.raises(ValueError, match='does not allow'):
        pull_data.scrape_new_data(set(), data_dir=tmp_path)


def test_pipeline_saves_data_and_falls_back(db_url, rows, tmp_path, monkeypatch):
    scraper = Mock(return_value=rows)
    monkeypatch.setattr(pull_data, 'scrape_new_data', scraper)
    monkeypatch.setattr(pull_data, 'add_llm_fields', lambda cleaned, cache: cleaned)
    cleaned, warning = pull_data.prepare_applicants(db_url, data_dir=tmp_path)
    assert len(cleaned) == 3
    assert warning == ''
    assert load_data(tmp_path / 'new_raw_data.json') == rows
    assert load_data(tmp_path / 'new_cleaned_data.json') == cleaned
    insert_applicants(rows, db_url)
    monkeypatch.setattr(pull_data, 'add_llm_fields', Mock(side_effect=RuntimeError('Model unavailable')))
    cleaned, warning = pull_data.prepare_applicants(db_url, data_dir=tmp_path)
    expected_urls = set()
    for applicant in rows:
        expected_urls.add(applicant['url'])
    assert scraper.call_args.args[0] == expected_urls
    assert 'LLM names were unavailable' in warning
    assert all(row['llm-generated-program'] is None for row in cleaned)
    scraper.return_value = []
    assert pull_data.prepare_applicants(db_url, data_dir=tmp_path) == ([], '')


def test_complete_pull_and_default_app_pipeline(db_url, rows, monkeypatch, tmp_path):
    monkeypatch.setattr(pull_data, 'RUNTIME', tmp_path)
    monkeypatch.setattr(pull_data, 'scrape_new_data', lambda *a: rows)
    monkeypatch.setattr(pull_data, 'add_llm_fields', lambda rows, cache: rows)
    assert pull_data.pull_new_data(database_url=db_url) == (3, '')
    assert len(applicant_records(db_url)) == 3
    def prepare_with_progress(database_url, report):
        report('Checking the next page.')
        assert app.extensions['gradcafe']['state']['message'] == 'Checking the next page.'
        return rows, 'Optional model unavailable'

    fake = Mock(side_effect=prepare_with_progress)
    monkeypatch.setattr('src.app.prepare_applicants', fake)
    app = create_app({'TESTING': True, 'DATABASE_URL': db_url, 'PULL_SYNCHRONOUS': True})
    assert app.test_client().post('/pull-data').status_code == 200
    fake.assert_called_once()
    assert len(applicant_records(db_url)) == 3
    assert 'Optional model unavailable' in app.extensions['gradcafe']['state']['message']


def test_end_of_pagination_without_existing_records(monkeypatch, tmp_path):
    configure_scrape(monkeypatch, [[{'url':'new'}]])
    assert pull_data.scrape_new_data(set(), data_dir=tmp_path) == [{'url':'new'}]
