"""The password loads from the saved local file outside this project.
Running python database.py only checks the connection.
"""

import json
import os
from pathlib import Path

SETTINGS_FILE = Path.home() / ".gradcafe" / "connection.json"

# The usual local PostgreSQL.
DEFAULT_SETTINGS = {
    "host": "localhost",
    "port": 5432,
    "dbname": "gradcafe",
    "user": "postgres",
    "password": "",
}


def database_settings():
    """Start with defaults, then read this computer's saved connection."""
    settings = DEFAULT_SETTINGS.copy()
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, encoding="utf-8") as file:
            settings.update(json.load(file))

    # Terminal settings still take priority, for example when running tests.
    variables = {
        "host": "PGHOST", "port": "PGPORT", "dbname": "PGDATABASE",
        "user": "PGUSER", "password": "PGPASSWORD",
    }
    for name, variable in variables.items():
        if variable in os.environ:
            settings[name] = os.environ[variable]

    settings["port"] = int(settings["port"])
    settings["connect_timeout"] = 5
    return settings


def check_connection():
    """Check the existing connection without asking for or changing settings."""
    import psycopg

    try:
        with psycopg.connect(**database_settings()):
            pass  # Check the connection without changing anything in the database.
    except (ValueError, psycopg.Error):
        raise SystemExit(
            "Could not connect. Check that PostgreSQL is running and that the "
            "database and saved password match the README connection settings."
        )
    print("Connected to PostgreSQL. You can run the project scripts normally.")


if __name__ == "__main__":
    check_connection()
