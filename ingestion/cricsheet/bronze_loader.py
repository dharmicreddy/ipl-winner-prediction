"""Cricsheet bronze loader.

Reads extracted JSON match files from disk and upserts them into
bronze.cricsheet_matches. Idempotent by design — re-running updates
rows rather than creating duplicates.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ingestion.cricsheet.downloader import EXTRACT_DIR
from ingestion.db.connection import get_connection

logger = logging.getLogger(__name__)

CRICSHEET_MATCH_URL_TEMPLATE = "https://cricsheet.org/matches/{match_id}.json"

UPSERT_SQL = """
    INSERT INTO bronze.cricsheet_matches (match_id, source_url, raw_content, ingested_at)
    VALUES (%s, %s, %s::jsonb, now())
    ON CONFLICT (match_id) DO UPDATE
    SET source_url  = EXCLUDED.source_url,
        raw_content = EXCLUDED.raw_content,
        ingested_at = EXCLUDED.ingested_at
"""


def _read_match_files(source_dir: Path) -> list[tuple[str, str, str]]:
    """Read match JSON files and prepare (match_id, source_url, raw_json_str) tuples.

    We store the JSON as a string and let Postgres cast to jsonb — avoids
    Python-side validation while still getting jsonb storage.
    """
    rows: list[tuple[str, str, str]] = []
    for path in sorted(source_dir.glob("*.json")):
        match_id = path.stem  # filename without .json
        raw_text = path.read_text(encoding="utf-8")
        # Parse once to validate it's real JSON; re-serialize to be safe.
        # (A file that doesn't parse has no business landing in bronze.)
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning("Skipping unparseable file %s: %s", path, exc)
            continue

        source_url = CRICSHEET_MATCH_URL_TEMPLATE.format(match_id=match_id)
        rows.append((match_id, source_url, json.dumps(parsed)))
    return rows


def load_bronze(source_dir: Path | None = None) -> int:
    """Upsert all match files from source_dir into bronze.cricsheet_matches.

    Returns the number of rows inserted or updated.
    """
    source_dir = source_dir or EXTRACT_DIR
    if not source_dir.exists():
        raise FileNotFoundError(
            f"Extract directory not found: {source_dir}. "
            "Run the downloader first: python -m ingestion.cricsheet.downloader"
        )

    rows = _read_match_files(source_dir)
    if not rows:
        logger.warning("No match files found in %s", source_dir)
        return 0

    logger.info("Upserting %d match files into bronze.cricsheet_matches", len(rows))
    with get_connection() as conn, conn.cursor() as cur:
        cur.executemany(UPSERT_SQL, rows)

    logger.info("Bronze load complete: %d rows", len(rows))
    return len(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    count = load_bronze()
    print(f"Loaded {count} matches into bronze")
