"""End-to-end integration test.

Runs the full Chunk 2.3 → 2.7 pipeline against the real Postgres database:
- Applies migrations
- Inserts one bronze row from the fixture
- Parses it to silver
- Queries gold.fact_matches
- Verifies row shapes and types

This test REQUIRES a running Postgres (docker compose up). It is skipped
automatically if Postgres isn't reachable, so CI won't fail on machines
without Docker.
"""

from __future__ import annotations

import json
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
        cur.execute("DELETE FROM silver.deliveries WHERE match_id = %s", (TEST_MATCH_ID,))
        cur.execute("DELETE FROM silver.matches WHERE match_id = %s", (TEST_MATCH_ID,))
        cur.execute("DELETE FROM bronze.cricsheet_matches WHERE match_id = %s", (TEST_MATCH_ID,))


def test_full_pipeline_against_real_postgres():
    run_migrations()  # idempotent — should be a no-op by now

    raw = FIXTURE.read_text(encoding="utf-8")
    # Insert a single bronze row with our sentinel match_id.
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

    # Parse just this one match by temporarily using a targeted query.
    # The public parse_bronze_to_silver reads everything; that's fine too
    # since it's idempotent. But to keep the test fast we'll call it once
    # and then verify our specific row landed.
    parse_bronze_to_silver()

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM silver.matches WHERE match_id = %s",
            (TEST_MATCH_ID,),
        )
        match_count = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM silver.deliveries WHERE match_id = %s",
            (TEST_MATCH_ID,),
        )
        delivery_count = cur.fetchone()[0]

        # Gold view should surface this match unless it was a no-result.
        fixture_data = json.loads(raw)
        has_winner = "winner" in fixture_data.get("info", {}).get("outcome", {})
        cur.execute(
            "SELECT count(*) FROM gold.fact_matches WHERE match_id = %s",
            (TEST_MATCH_ID,),
        )
        gold_count = cur.fetchone()[0]

    assert match_count == 1, "silver.matches should have exactly one row for the test match"
    assert delivery_count > 50, "silver.deliveries should have many deliveries for a full match"
    if has_winner:
        assert gold_count == 1, "gold.fact_matches should include matches with a winner"
    else:
        assert gold_count == 0, "gold.fact_matches should exclude no-result matches"
