"""CricketData.org fixtures parser.

Reads bronze.http_responses rows where source='cricketdata', validates each
match via pydantic, and upserts silver_raw.fixtures.

IPL detection is heuristic: any match whose `name` contains "Indian Premier
League" (case-insensitive) is tagged is_ipl=true. The alternative — resolving
series_id via a separate API call — is deferred to a later phase if needed.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ingestion.cricketdata.schemas import CricketDataMatch, CricketDataResponse
from ingestion.db.connection import get_connection

logger = logging.getLogger(__name__)


SELECT_BRONZE_SQL = """
    SELECT response_id, response_body
    FROM bronze.http_responses
    WHERE source = 'cricketdata'
      AND status_code = 200
      AND response_body IS NOT NULL
    ORDER BY fetched_at ASC
"""

FIXTURE_UPSERT_SQL = """
    INSERT INTO silver_raw.fixtures (
        fixture_id, match_name, match_type, status,
        venue, match_date, series_name,
        team_1, team_2, is_ipl, raw_response_id
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (fixture_id) DO UPDATE SET
        match_name       = EXCLUDED.match_name,
        match_type       = EXCLUDED.match_type,
        status           = EXCLUDED.status,
        venue            = EXCLUDED.venue,
        match_date       = EXCLUDED.match_date,
        series_name      = EXCLUDED.series_name,
        team_1           = EXCLUDED.team_1,
        team_2           = EXCLUDED.team_2,
        is_ipl           = EXCLUDED.is_ipl,
        raw_response_id  = EXCLUDED.raw_response_id,
        parsed_at        = now()
"""


# "IPL " with trailing space to avoid "IPL3"-style false positives.
IPL_MARKERS = ("indian premier league", "ipl ")


def _is_ipl(name: str) -> bool:
    lower = name.lower()
    return any(marker in lower for marker in IPL_MARKERS)


def _extract_series_name(match_name: str) -> str | None:
    """The match 'name' field is a comma-separated string like:
       'Team A vs Team B, 12th Match, Series Name 2026'.
    We take the last comma-separated segment as the series name."""
    parts = [p.strip() for p in match_name.split(",")]
    return parts[-1] if parts else None


def _parse_match_datetime(match: CricketDataMatch) -> datetime | None:
    """Prefer dateTimeGMT; fall back to date-only."""
    if match.dateTimeGMT:
        try:
            return datetime.fromisoformat(match.dateTimeGMT)
        except ValueError:
            pass
    if match.date:
        try:
            return datetime.fromisoformat(match.date)
        except ValueError:
            return None
    return None


def parse_match(response_id: int, match: CricketDataMatch) -> tuple:
    """Build a silver.fixtures row tuple."""
    team_1 = match.teams[0] if len(match.teams) > 0 else None
    team_2 = match.teams[1] if len(match.teams) > 1 else None
    match_date = _parse_match_datetime(match)
    series_name = _extract_series_name(match.name)

    return (
        match.id,
        match.name,
        match.matchType,
        match.status,
        match.venue,
        match_date,
        series_name,
        team_1,
        team_2,
        _is_ipl(match.name),
        response_id,
    )


def parse_bronze_to_silver() -> dict[str, int]:
    """Parse all CricketData bronze rows into silver_raw.fixtures.

    Returns counts: {"rows_written": N, "ipl_rows": K, "errors": E}.
    """
    rows_written = 0
    ipl_rows = 0
    errors = 0

    with get_connection() as conn:
        with conn.cursor() as read_cur:
            read_cur.execute(SELECT_BRONZE_SQL)
            bronze_rows = read_cur.fetchall()

        logger.info("Parsing %d CricketData bronze rows", len(bronze_rows))

        with conn.cursor() as write_cur:
            for response_id, response_body in bronze_rows:
                # psycopg returns jsonb as a dict already.
                body: dict[str, Any] = response_body if isinstance(response_body, dict) else {}
                try:
                    parsed = CricketDataResponse.model_validate(body)
                except Exception as exc:
                    logger.warning("Response %d failed validation: %s", response_id, exc)
                    errors += 1
                    continue

                for match in parsed.data:
                    try:
                        row = parse_match(response_id, match)
                    except Exception as exc:
                        logger.warning("Match %s failed to parse: %s", match.id, exc)
                        errors += 1
                        continue

                    write_cur.execute(FIXTURE_UPSERT_SQL, row)
                    rows_written += 1
                    if row[9]:  # is_ipl
                        ipl_rows += 1

    logger.info(
        "Silver fixtures parse complete: %d rows (%d IPL), %d errors",
        rows_written,
        ipl_rows,
        errors,
    )
    return {"rows_written": rows_written, "ipl_rows": ipl_rows, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = parse_bronze_to_silver()
    print(
        f"Wrote {result['rows_written']} rows ({result['ipl_rows']} IPL, {result['errors']} errors)"
    )
