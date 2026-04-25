"""CricketData.org fixtures client.

Fetches the currentMatches endpoint — a list of recent and upcoming matches
across all cricket formats. The parser filters to IPL in silver_raw.

Free tier constraints:
- Requires API key (CRICKETDATA_API_KEY env var)
- 30-second data lag for registered users
- Rate limits are generous; we still throttle politely

Endpoint: https://api.cricapi.com/v1/currentMatches
Docs: https://cricketdata.org/docs/
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from ingestion.http.bronze_writer import land_response
from ingestion.http.client import HTTPClient
from ingestion.http.rate_limiter import TokenBucket

logger = logging.getLogger(__name__)
# Silence httpx INFO logging — it prints full URLs including the apikey query param.
logging.getLogger("httpx").setLevel(logging.WARNING)


load_dotenv()

SOURCE = "cricketdata"
CURRENT_MATCHES_URL = "https://api.cricapi.com/v1/currentMatches"

# Generous rate cap — we make only a handful of calls per run.
RATE_PER_SECOND = 2.0
BURST = 4

# CricketData paginates with offset. Free tier returns 25 per page.
PAGE_SIZE = 25
MAX_PAGES = 4  # up to 100 matches per run; plenty for weekly cadence


def _api_key() -> str:
    key = os.getenv("CRICKETDATA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("CRICKETDATA_API_KEY not set. Add it to .env (see .env.example).")
    return key


def fetch_current_matches() -> dict[str, int]:
    """Fetch up to MAX_PAGES of current matches and land each page to bronze.

    Returns counts: {"pages_fetched": N, "errors": K}.
    """
    api_key = _api_key()
    rate_limiter = TokenBucket(rate_per_second=RATE_PER_SECOND, burst=BURST)

    pages_fetched = 0
    errors = 0

    with HTTPClient(rate_limiter=rate_limiter) as client:
        for page in range(MAX_PAGES):
            offset = page * PAGE_SIZE
            params = {"apikey": api_key, "offset": offset}
            try:
                response = client.get(CURRENT_MATCHES_URL, params=params)
            except Exception as exc:
                logger.error("Failed to fetch page %d: %s", page, exc)
                errors += 1
                break

            if response.status_code >= 400:
                logger.warning(
                    "Got status %s on page %d — stopping",
                    response.status_code,
                    page,
                )
                errors += 1
                break

            # CricketData wraps the list in {"status": "success", "data": [...]}
            body = response.json_body or {}
            data = body.get("data") or []
            logger.info("Page %d: got %d matches", page, len(data))

            land_response(SOURCE, response)
            pages_fetched += 1

            # If the page isn't full, we're at the end.
            if len(data) < PAGE_SIZE:
                break

    logger.info(
        "CricketData fetch complete: %d pages fetched, %d errors",
        pages_fetched,
        errors,
    )
    return {"pages_fetched": pages_fetched, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = fetch_current_matches()
    print(f"Fetched {result['pages_fetched']} pages ({result['errors']} errors)")
