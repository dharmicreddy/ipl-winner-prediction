"""Data access layer for the dashboard.

Auto-detects backend at module load:
- If POSTGRES_HOST env var is set (local development), connects to Postgres.
- Otherwise (Streamlit Cloud), reads from a bundled SQLite snapshot at
  dashboard/data/ipl.sqlite.

The same query strings work against both backends — gold.fact_matches in
Postgres is mirrored as a `gold__fact_matches` table in SQLite (SQLite
doesn't support schemas, so we flatten with the `__` separator).
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

# Detection: prefer Postgres if its config is in the environment.
_USE_POSTGRES = bool(os.getenv("POSTGRES_HOST"))

# Path to the bundled SQLite snapshot, used when Postgres is unavailable.
_SQLITE_PATH = Path(__file__).resolve().parent.parent / "data" / "ipl.sqlite"


@contextmanager
def _connection():
    """Yield a DB connection appropriate to the current backend."""
    if _USE_POSTGRES:
        # Local dev: use the same connection helper as the ingestion code.
        from ingestion.db.connection import get_connection

        with get_connection() as conn:
            yield conn
    else:
        # Cloud / fallback: read-only SQLite.
        if not _SQLITE_PATH.exists():
            raise FileNotFoundError(
                f"SQLite snapshot not found at {_SQLITE_PATH}. "
                "Run `python -m scripts.build_dashboard_assets` to generate it."
            )
        conn = sqlite3.connect(str(_SQLITE_PATH))
        try:
            yield conn
        finally:
            conn.close()


def _rewrite_for_sqlite(query: str) -> str:
    """Translate a Postgres-style query to SQLite-style.

    SQLite has no schemas, so `gold.fact_matches` becomes `gold__fact_matches`.
    """
    return (
        query.replace("gold.fact_matches", "gold__fact_matches")
        .replace("gold.upcoming_ipl_matches", "gold__upcoming_ipl_matches")
        .replace("gold.dim_teams", "gold__dim_teams")
        .replace("gold.dim_venues", "gold__dim_venues")
        .replace("features.features__match_set", "features__match_set")
    )


def query(sql: str) -> pd.DataFrame:
    """Run a SQL query against whichever backend is configured.

    The query should be written in Postgres style (with schema prefixes).
    For SQLite, prefixes are auto-translated.
    """
    sql_to_run = sql if _USE_POSTGRES else _rewrite_for_sqlite(sql)
    with _connection() as conn:
        return pd.read_sql(sql_to_run, conn)


def get_backend_name() -> str:
    """Returns 'postgres' or 'sqlite' for use in dashboard footer/debug."""
    return "postgres" if _USE_POSTGRES else "sqlite"
