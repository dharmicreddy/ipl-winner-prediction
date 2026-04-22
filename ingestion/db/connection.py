"""
Loads credentials from environment variables (via python-dotenv in local dev)
and provides a simple factory for psycopg connections.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv

load_dotenv()  # pick up .env in local dev; no-op in prod where env is set directly


def _build_conninfo() -> str:
    """Build a libpq-style connection string from POSTGRES_* env vars."""
    required = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            f"Missing required env vars: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in local values."
        )
    return (
        f"host={os.environ['POSTGRES_HOST']} "
        f"port={os.environ['POSTGRES_PORT']} "
        f"dbname={os.environ['POSTGRES_DB']} "
        f"user={os.environ['POSTGRES_USER']} "
        f"password={os.environ['POSTGRES_PASSWORD']}"
    )


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Yield a psycopg connection. Commits on clean exit, rolls back on exception."""
    conn = psycopg.connect(_build_conninfo())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
