"""Wikipedia venue parser.

Reads the latest bronze.http_responses row per URL (source='wikipedia'),
validates the payload via pydantic, and upserts silver_raw.venues plus
silver_raw.venue_aliases (the Cricsheet-spelling to canonical mapping).
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from ingestion.db.connection import get_connection
from ingestion.wikipedia.schemas import WikipediaSummary

logger = logging.getLogger(__name__)

VENUES_YAML = Path(__file__).resolve().parents[1] / "reference" / "ipl_venues.yaml"


SELECT_LATEST_SQL = """
    SELECT DISTINCT ON (url)
        response_id, url, response_body, content_sha256
    FROM bronze.http_responses
    WHERE source = 'wikipedia' AND status_code = 200 AND response_body IS NOT NULL
    ORDER BY url, fetched_at DESC
"""

VENUE_UPSERT_SQL = """
    INSERT INTO silver_raw.venues (
        wiki_title, display_title, description, extract,
        latitude, longitude, wikipedia_url,
        content_sha256, raw_response_id
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (wiki_title) DO UPDATE SET
        display_title   = EXCLUDED.display_title,
        description     = EXCLUDED.description,
        extract         = EXCLUDED.extract,
        latitude        = EXCLUDED.latitude,
        longitude       = EXCLUDED.longitude,
        wikipedia_url   = EXCLUDED.wikipedia_url,
        content_sha256  = EXCLUDED.content_sha256,
        raw_response_id = EXCLUDED.raw_response_id,
        parsed_at       = now()
"""

ALIAS_UPSERT_SQL = """
    INSERT INTO silver_raw.venue_aliases (venue_alias, wiki_title)
    VALUES (%s, %s)
    ON CONFLICT (venue_alias) DO UPDATE SET wiki_title = EXCLUDED.wiki_title
"""


def _wiki_title_from_url(url: str) -> str:
    """Extract the wiki_title from a Wikipedia summary URL."""
    return url.rsplit("/", 1)[-1]


def parse_venue(response_id: int, url: str, body: dict, content_sha256: str) -> tuple:
    """Build a silver.venues row tuple from a bronze response."""
    summary = WikipediaSummary.model_validate(body)
    lat = summary.coordinates.lat if summary.coordinates else None
    lon = summary.coordinates.lon if summary.coordinates else None
    wiki_title = _wiki_title_from_url(url)

    return (
        wiki_title,
        summary.title,
        summary.description,
        summary.extract,
        lat,
        lon,
        summary.get_wikipedia_url(),
        content_sha256,
        response_id,
    )


def _load_aliases() -> list[tuple[str, str]]:
    """Return [(cricsheet_venue_spelling, wiki_title), ...] from the YAML."""
    with VENUES_YAML.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [(entry["venue"], entry["wiki_title"]) for entry in data.get("venues", [])]


def parse_bronze_to_silver() -> dict[str, int]:
    """Parse Wikipedia bronze rows into silver.venues + silver.venue_aliases."""
    venues_written = 0
    aliases_written = 0
    errors = 0

    with get_connection() as conn:
        with conn.cursor() as read_cur:
            read_cur.execute(SELECT_LATEST_SQL)
            bronze_rows = read_cur.fetchall()

        logger.info("Parsing %d Wikipedia bronze rows into silver_raw.venues", len(bronze_rows))

        with conn.cursor() as write_cur:
            for response_id, url, body, sha in bronze_rows:
                try:
                    row = parse_venue(response_id, url, body, sha)
                except Exception as exc:
                    logger.warning("Failed to parse %s: %s", url, exc)
                    errors += 1
                    continue

                write_cur.execute(VENUE_UPSERT_SQL, row)
                venues_written += 1

            # Insert aliases last so the FK to silver.venues is satisfied.
            aliases = _load_aliases()
            for alias, wiki_title in aliases:
                write_cur.execute(ALIAS_UPSERT_SQL, (alias, wiki_title))
                aliases_written += 1

    logger.info(
        "Silver venue parse complete: %d venues, %d aliases, %d errors",
        venues_written,
        aliases_written,
        errors,
    )
    return {"venues": venues_written, "aliases": aliases_written, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = parse_bronze_to_silver()
    print(
        f"Parsed {result['venues']} venues, {result['aliases']} aliases ({result['errors']} errors)"
    )
