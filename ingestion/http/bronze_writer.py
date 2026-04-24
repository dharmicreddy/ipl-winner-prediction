"""Write FetchedResponse into bronze.http_responses."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from psycopg.types.json import Json

from ingestion.db.connection import get_connection
from ingestion.http.client import FetchedResponse

logger = logging.getLogger(__name__)


INSERT_SQL = """
    INSERT INTO bronze.http_responses (
        source, url, status_code,
        response_body, response_text,
        content_sha256, headers, fetched_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, now())
    RETURNING response_id
"""


def land_response(source: str, response: FetchedResponse) -> int:
    """Insert a FetchedResponse into bronze.http_responses. Returns the new row's id."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            INSERT_SQL,
            (
                source,
                response.url,
                response.status_code,
                Json(response.json_body) if response.json_body is not None else None,
                response.text if response.json_body is None else None,
                response.content_sha256,
                Json(response.headers),
            ),
        )
        (response_id,) = cur.fetchone()
    # Strip query string to avoid leaking API keys in logs. Full URL stays in bronze.
    parsed = urlparse(response.url)
    loggable_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    logger.info("Landed %s response for %s -> bronze row %d", source, loggable_url, response_id)
    return response_id
