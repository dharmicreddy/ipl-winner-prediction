"""End-to-end integration test.

Runs the full Chunk 2.3 -> 2.7 pipeline against the real Postgres database:
- Applies migrations
- Inserts one bronze row from the fixture
- Parses it to silver_raw
- Verifies row shapes and types

Gold.fact_matches checks are disabled during Phase 4 migration — dbt will
rebuild gold.fact_matches in Chunk 4.3, at which point we re-enable them.

Requires a running Postgres. Skipped automatically otherwise.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from ingestion.cricsheet.silver_parser import parse_bronze_to_silver
from ingestion.db.connection import get_connection
from ingestion.db.migrate import run_migrations

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_match.json"
TEST_MATCH_ID = "_integration_test_match"


def _postgres_available() -> bool:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except (psycopg.Error, RuntimeError, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="Postgres not reachable — skip integration test",
)


@pytest.fixture(autouse=True)
def _cleanup():
    """Remove any lingering test rows before and after."""
    yield
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM silver_raw.deliveries WHERE match_id = %s", (TEST_MATCH_ID,))
        cur.execute("DELETE FROM silver_raw.matches WHERE match_id = %s", (TEST_MATCH_ID,))
        cur.execute("DELETE FROM bronze.cricsheet_matches WHERE match_id = %s", (TEST_MATCH_ID,))


def test_full_pipeline_against_real_postgres():
    run_migrations()

    raw = FIXTURE.read_text(encoding="utf-8")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bronze.cricsheet_matches
                (match_id, source_url, raw_content, ingested_at)
            VALUES (%s, %s, %s::jsonb, now())
            ON CONFLICT (match_id) DO UPDATE
            SET raw_content = EXCLUDED.raw_content, ingested_at = now()
            """,
            (TEST_MATCH_ID, "https://example/integration", raw),
        )

    parse_bronze_to_silver()

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM silver_raw.matches WHERE match_id = %s",
            (TEST_MATCH_ID,),
        )
        match_count = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM silver_raw.deliveries WHERE match_id = %s",
            (TEST_MATCH_ID,),
        )
        delivery_count = cur.fetchone()[0]

    assert match_count == 1
    assert delivery_count > 50

    # Gold assertions disabled during Phase 4 migration.
    # dbt will rebuild gold.fact_matches in Chunk 4.3; re-enable then.
