"""These assertions exercise real PostgreSQL, including transaction rollback."""
import pytest
import psycopg
from decimal import Decimal
from unittest.mock import Mock
from src.app import create_app
from src.load_data import insert_applicants, applicant_records, number_or_none, text_or_none
from src.query_data import run_queries
from src.orm_queries import run_orm_queries

pytestmark = pytest.mark.db

FIELDS = {'p_id', 'program', 'comments', 'date_added', 'url', 'status', 'term', 'us_or_international',
          'gpa', 'gre', 'gre_v', 'gre_aw', 'degree', 'llm_generated_program', 'llm_generated_university'}


def test_pull_inserts_required_fields(db_url, rows):
    assert applicant_records(db_url) == []
    app = create_app(
        {'TESTING': True, 'DATABASE_URL': db_url, 'PULL_SYNCHRONOUS': True},
        scraper=Mock(return_value=rows),
    )
    assert app.test_client().post('/pull-data').status_code == 200
    stored = applicant_records(db_url)
    assert len(stored) == 3
    assert set(stored[0]) == FIELDS
    for applicant in stored:
        assert applicant['p_id'] is not None
        assert applicant['url']
    assert stored[0]['status'] == 'Accepted'
    assert stored[0]['gpa'] == 4
    assert stored[0]['degree'] == 'Masters'
    assert str(stored[0]['date_added']) == '2026-09-20'
    assert stored[0]['llm_generated_university'] == 'Johns Hopkins University'


def test_idempotency_and_missing_urls(db_url, rows):
    assert insert_applicants(rows + [{'url': None}], db_url) == (3, 1)
    assert insert_applicants(rows, db_url) == (0, 0)
    assert len(applicant_records(db_url)) == 3
    assert insert_applicants([], db_url) == (0, 0)
    with psycopg.connect(db_url) as connection:
        with pytest.raises(psycopg.errors.NotNullViolation):
            connection.execute('INSERT INTO applicants (url) VALUES (NULL)')


def test_loader_error_rolls_back_entire_batch(db_url, rows):
    # PostgreSQL rejects this NUL character. Even the valid first row must
    # disappear when the transaction (the complete batch of writes) fails.
    invalid_applicant = rows[1].copy()
    invalid_applicant['program'] = 'bad\x00text'
    app = create_app(
        {'TESTING': True, 'DATABASE_URL': db_url, 'PULL_SYNCHRONOUS': True},
        scraper=Mock(return_value=[rows[0], invalid_applicant]),
    )
    assert app.test_client().post('/pull-data').status_code == 500
    assert applicant_records(db_url) == []


def test_expected_query_keys_and_sql_orm_agree(db_url, rows):
    insert_applicants(rows, db_url)
    raw = run_queries(db_url)
    orm = run_orm_queries(db_url)
    assert set(raw) == set(range(1, 12)) == set(orm)
    for number in raw:
        for sql_row, orm_row in zip(raw[number], orm[number], strict=True):
            for sql_value, orm_value in zip(sql_row, orm_row, strict=True):
                if isinstance(sql_value, (int, float, Decimal)):
                    # Floating-point answers can differ by a tiny amount.
                    assert float(sql_value) == pytest.approx(float(orm_value))
                else:
                    assert sql_value == orm_value
    assert raw[1] == [(2,)]
    assert float(raw[2][0][0]) == pytest.approx(100 / 3)
    assert raw[3] == [(3.0, 160.0, 155.0, 4.0)]
    assert raw[7] == [(1,)]
    assert raw[8] == [(1,)]
    assert raw[9] == [(1, 1, 0)]


@pytest.mark.parametrize('value', [None, '', 'bad', float('inf'), float('nan')])
def test_bad_numbers_are_null(value):
    assert number_or_none(value) is None


def test_null_text():
    assert text_or_none(None) is None
    assert text_or_none(' ') is None
    assert text_or_none(' x ') == 'x'
