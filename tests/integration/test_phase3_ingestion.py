"""End-to-end integration test for Phase 3 ingestion.

Does NOT hit external APIs. Uses cached bronze fixtures inserted directly
into a running Postgres, then drives the parsers and checks gold views.

Skipped automatically if Postgres isn't reachable.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import psycopg
import pytest

from ingestion.cricketdata.fixtures_parser import (
    parse_bronze_to_silver as parse_cricketdata,
)
from ingestion.db.connection import get_connection
from ingestion.db.migrate import run_migrations
from ingestion.wikipedia.venue_parser import parse_bronze_to_silver as parse_wikipedia

WIKI_FIXTURE = Path(__file__).parent.parent / "fixtures" / "wikipedia_wankhede.json"
CRICKETDATA_FIXTURE = Path(__file__).parent.parent / "fixtures" / "cricketdata_current_matches.json"

# Sentinels so we can clean up after ourselves.
WIKI_TEST_URL = (
    "https://en.wikipedia.org/api/rest_v1/page/summary/Wankhede_Stadium_TEST_INTEGRATION"
)
CRICKETDATA_TEST_URL = "https://api.cricapi.com/v1/currentMatches?test=integration"


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
    """Remove anything our test inserted, in FK-safe order."""
    yield
    with get_connection() as conn, conn.cursor() as cur:
        # Delete silver first (child rows), then bronze (parents).
        cur.execute(
            """
            DELETE FROM silver.fixtures
            WHERE raw_response_id IN (
                SELECT response_id FROM bronze.http_responses WHERE url = %s
            )
            """,
            (CRICKETDATA_TEST_URL,),
        )
        cur.execute(
            "DELETE FROM silver.venues WHERE wiki_title = %s",
            ("Wankhede_Stadium_TEST_INTEGRATION",),
        )
        cur.execute(
            "DELETE FROM bronze.http_responses WHERE url IN (%s, %s)",
            (WIKI_TEST_URL, CRICKETDATA_TEST_URL),
        )


def _insert_bronze(source: str, url: str, body: dict) -> int:
    body_text = json.dumps(body)
    sha = hashlib.sha256(body_text.encode()).hexdigest()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bronze.http_responses
                (source, url, status_code, response_body, content_sha256, headers, fetched_at)
            VALUES (%s, %s, 200, %s::jsonb, %s, '{}'::jsonb, now())
            RETURNING response_id
            """,
            (source, url, body_text, sha),
        )
        (response_id,) = cur.fetchone()
    return response_id


def test_wikipedia_pipeline_end_to_end():
    run_migrations()

    body = json.loads(WIKI_FIXTURE.read_text(encoding="utf-8"))
    _insert_bronze("wikipedia", WIKI_TEST_URL, body)

    result = parse_wikipedia()
    assert result["venues"] >= 1
    assert result["errors"] == 0

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT display_title, latitude FROM silver.venues WHERE wiki_title = %s",
            ("Wankhede_Stadium_TEST_INTEGRATION",),
        )
        row = cur.fetchone()
    assert row is not None
    display_title, lat = row
    assert display_title  # at least some title
    assert lat is not None  # Wankhede has coords in our fixture


def test_cricketdata_pipeline_end_to_end():
    run_migrations()

    body = json.loads(CRICKETDATA_FIXTURE.read_text(encoding="utf-8"))
    _insert_bronze("cricketdata", CRICKETDATA_TEST_URL, body)

    result = parse_cricketdata()
    assert result["rows_written"] > 0
    assert result["errors"] == 0
