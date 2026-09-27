"""Portable PostgreSQL connections; importing this module never connects."""
import os
import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


def database_url(value=None):
    """Read an explicit URL or DATABASE_URL, never a personal password file."""
    if not value:
        value = os.environ.get("DATABASE_URL")
    if not value:
        raise ValueError("Set DATABASE_URL to a PostgreSQL connection URL.")
    parsed_url = make_url(value)
    if parsed_url.drivername not in ("postgresql", "postgresql+psycopg"):
        raise ValueError("DATABASE_URL must use PostgreSQL.")
    return parsed_url.set(drivername="postgresql").render_as_string(hide_password=False)


def connect(value=None):
    """Return a psycopg connection; use its context manager for atomic writes."""
    return psycopg.connect(database_url(value), connect_timeout=5)


def make_engine(value=None):
    """Create a short-lived SQLAlchemy engine for PostgreSQL queries."""
    url = make_url(database_url(value)).set(drivername="postgresql+psycopg")
    return create_engine(url, connect_args={"connect_timeout": 5})


def check_connection():
    """Verify configured access without changing any tables."""
    with connect():
        pass
    print("Connected to PostgreSQL.")


if __name__ == "__main__":
    check_connection()
