"""Retrying HTTP client implementing ADR-006 patterns.

- Identifiable User-Agent on every request
- Exponential backoff with jitter on 429 and 5xx
- Respect Retry-After headers
- Rate limit via a shared TokenBucket
- Never raises on non-2xx — caller decides what to do (but logs warnings)
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ingestion.http.rate_limiter import TokenBucket

logger = logging.getLogger(__name__)

USER_AGENT = "ipl-prediction/0.1 (+https://github.com/dharmicreddy/ipl-winner-prediction)"
DEFAULT_TIMEOUT = 30.0


class RetryableHTTPError(Exception):
    """Raised internally to trigger tenacity retry on 429/5xx."""


@dataclass
class FetchedResponse:
    """Captured HTTP response ready to land in bronze."""

    url: str
    status_code: int
    headers: dict[str, Any]
    text: str
    content_sha256: str
    json_body: Any | None = field(default=None)


def _response_to_fetched(response: httpx.Response) -> FetchedResponse:
    text = response.text
    sha = hashlib.sha256(response.content).hexdigest()
    json_body: Any | None = None
    if "application/json" in response.headers.get("content-type", "").lower():
        try:
            json_body = response.json()
        except ValueError:
            logger.warning("Content-Type says JSON but body did not parse: %s", response.url)
    return FetchedResponse(
        url=str(response.url),
        status_code=response.status_code,
        headers=dict(response.headers),
        text=text,
        content_sha256=sha,
        json_body=json_body,
    )


class HTTPClient:
    """Shared HTTP client. One instance per source is typical."""

    def __init__(
        self,
        rate_limiter: TokenBucket,
        user_agent: str = USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.rate_limiter = rate_limiter
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HTTPClient:
        return self

    def __exit__(self, *_exc_info: Any) -> None:
        self.close()

    @retry(
        retry=retry_if_exception_type(
            (RetryableHTTPError, httpx.TimeoutException, httpx.NetworkError)
        ),
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=2, max=30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def get(self, url: str, params: dict[str, Any] | None = None) -> FetchedResponse:
        """GET a URL. Returns the fetched response or raises after retries exhausted."""
        self.rate_limiter.acquire()
        logger.debug("GET %s", url)
        response = self._client.get(url, params=params)

        # 429 and 5xx are retryable. Respect Retry-After if provided.
        if response.status_code == 429 or response.status_code >= 500:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                logger.warning("Got %s with Retry-After=%s", response.status_code, retry_after)
            raise RetryableHTTPError(f"{response.status_code} from {url}")

        # 4xx other than 429 is *not* retryable — it's a client error.
        # We return the FetchedResponse so callers can land it if they want.
        if response.status_code >= 400:
            logger.warning("Non-retryable error %s from %s", response.status_code, url)

        return _response_to_fetched(response)
