"""Wikipedia venue client.

Reads ipl_venues.yaml, dedupes by wiki_title, fetches each venue's summary
from the Wikipedia REST API, and lands the raw JSON response in
bronze.http_responses.

Uses the shared HTTP framework (ingestion.http) for rate limiting, retries,
and idempotent bronze landing.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from ingestion.http.bronze_writer import land_response
from ingestion.http.client import HTTPClient
from ingestion.http.rate_limiter import TokenBucket

logger = logging.getLogger(__name__)
# Silence httpx INFO logging — it prints full URLs. Harmless for Wikipedia
# (no API key in use) but kept for consistency with other clients.
logging.getLogger("httpx").setLevel(logging.WARNING)

SOURCE = "wikipedia"
WIKI_SUMMARY_URL_TEMPLATE = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

# Wikipedia allows 200 req/s per IP. We use a conservative 5 req/s.
RATE_PER_SECOND = 5.0
BURST = 10

VENUES_YAML = Path(__file__).resolve().parents[1] / "reference" / "ipl_venues.yaml"


def _load_wiki_titles() -> list[str]:
    """Read the venues YAML and return deduplicated wiki_title values."""
    with VENUES_YAML.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    titles = {entry["wiki_title"] for entry in data.get("venues", [])}
    return sorted(titles)


def fetch_all_venues() -> dict[str, int]:
    """Fetch every unique Wikipedia venue page and land to bronze.

    Returns counts: {"fetched": N, "errors": K}.
    """
    titles = _load_wiki_titles()
    logger.info("Fetching %d unique Wikipedia venue pages", len(titles))

    rate_limiter = TokenBucket(rate_per_second=RATE_PER_SECOND, burst=BURST)
    fetched = 0
    errors = 0

    with HTTPClient(rate_limiter=rate_limiter) as client:
        for title in titles:
            url = WIKI_SUMMARY_URL_TEMPLATE.format(title=title)
            try:
                response = client.get(url)
            except Exception as exc:
                logger.error("Failed to fetch %s: %s", url, exc)
                errors += 1
                continue

            if response.status_code >= 400:
                logger.warning("Got %s for %s — skipping bronze landing", response.status_code, url)
                errors += 1
                continue

            land_response(SOURCE, response)
            fetched += 1

    logger.info("Wikipedia venue fetch complete: %d fetched, %d errors", fetched, errors)
    return {"fetched": fetched, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = fetch_all_venues()
    print(f"Fetched {result['fetched']} venues ({result['errors']} errors)")
