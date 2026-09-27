"""Deterministic fakes and a separate PostgreSQL schema for every DB test."""
import os
import uuid
from urllib.request import OpenerDirector
import psycopg
from psycopg import sql
import pytest
from sqlalchemy.engine import make_url
from src.load_data import CREATE_TABLE

MARKERS = {"web", "buttons", "analysis", "db", "integration"}


def pytest_collection_modifyitems(items):
    """Pytest calls this function after finding the test functions."""
    unmarked = []
    for test in items:
        has_assignment_marker = False
        for marker in test.iter_markers():
            if marker.name in MARKERS:
                has_assignment_marker = True
                break
        if not has_assignment_marker:
            unmarked.append(test.nodeid)
    if unmarked:
        raise pytest.UsageError("Every test needs an assignment marker: " + ", ".join(unmarked))


@pytest.fixture(autouse=True)
def no_live_scraping(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Tests must use saved HTML or an injected scraper, never live requests.")
    monkeypatch.setattr(OpenerDirector, "open", forbidden)


@pytest.fixture
def rows():
    """A fixture is reusable test setup. This one provides three example rows."""
    return [
        {"program": "Computer Science, Johns Hopkins University", "url": "https://www.thegradcafe.com/result/1001",
         "comments": "Fixture one", "date_added": "September 20, 2026", "status": "Accepted on September 19, 2026",
         "term": "Fall 2026", "US/International": "American", "Degree": "Masters",
         "GPA": 4.0, "GRE": 165, "GRE V": 160, "GRE AW": 4.5,
         "llm-generated-program": "Computer Science", "llm-generated-university": "Johns Hopkins University"},
        {"program": "Computer Science, MIT", "url": "https://www.thegradcafe.com/result/1002",
         "comments": "Fixture two", "date_added": "September 21, 2026", "status": "Accepted", "term": "Fall 2026",
         "US/International": "International", "Degree": "PhD", "GPA": 3.0, "GRE": 155, "GRE V": 150, "GRE AW": 3.5,
         "llm-generated-program": "Computer Science", "llm-generated-university": "Massachusetts Institute of Technology"},
        {"program": "History, Example University", "url": "https://www.thegradcafe.com/result/1003",
         "comments": "Fixture three", "date_added": "September 22, 2026", "status": "Rejected", "term": "Fall 2025",
         "US/International": "Other", "Degree": "PhD", "GPA": 2.0}
    ]


@pytest.fixture
def db_url(monkeypatch):
    """Give this test its own temporary schema inside the test database."""
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.fail("Set TEST_DATABASE_URL to a dedicated PostgreSQL database ending in _test; DB tests are never skipped.")
    url = make_url(value)
    if url.drivername != "postgresql" or not (url.database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must be a postgresql:// URL to a database ending in _test.")
    # A schema is a group of tables. The random name keeps tests separate.
    schema = "m4_" + uuid.uuid4().hex
    with psycopg.connect(value, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    isolated = url.update_query_dict({"options": "-csearch_path=" + schema}).render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", isolated)
    try:
        with psycopg.connect(isolated) as connection:
            connection.execute(CREATE_TABLE)
        yield isolated  # Pytest runs the test here, then returns for cleanup.
    finally:
        with psycopg.connect(value, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
