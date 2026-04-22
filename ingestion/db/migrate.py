"""Apply SQL migrations from ingestion/db/migrations/ in order.

Usage:
    python -m ingestion.db.migrate
"""

from __future__ import annotations

import logging
from pathlib import Path

from ingestion.db.connection import get_connection

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _applied_versions(conn) -> set[str]:
    """Return the set of migration versions already applied."""
    with conn.cursor() as cur:
        # schema_migrations may not exist on a fresh DB, so create it defensively.
        cur.execute(
            "CREATE TABLE IF NOT EXISTS public.schema_migrations ("
            "  version text PRIMARY KEY,"
            "  applied_at timestamptz NOT NULL DEFAULT now()"
            ")"
        )
        cur.execute("SELECT version FROM public.schema_migrations")
        return {row[0] for row in cur.fetchall()}


def run_migrations() -> None:
    """Apply every .sql file in migrations/ that hasn't been applied yet."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        logger.warning("No migration files found in %s", MIGRATIONS_DIR)
        return

    with get_connection() as conn:
        applied = _applied_versions(conn)
        for path in files:
            version = path.stem  # e.g. "001_initial_schemas"
            if version in applied:
                logger.info("Skipping already-applied migration: %s", version)
                continue

            logger.info("Applying migration: %s", version)
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
            # Each migration's SQL should itself INSERT into schema_migrations.
            # We don't insert here to avoid duplicating the record.


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_migrations()
