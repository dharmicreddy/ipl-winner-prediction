"""Unit tests for the token-bucket rate limiter."""

from __future__ import annotations

import time

import pytest

from ingestion.http.rate_limiter import TokenBucket


def test_initial_burst_is_immediate():
    """Up to `burst` tokens should be available with no wait."""
    bucket = TokenBucket(rate_per_second=1, burst=3)
    start = time.monotonic()
    for _ in range(3):
        bucket.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 0.05  # essentially no delay


def test_fourth_call_blocks_until_refill():
    """With rate=10/s and burst=3, the 4th call should wait ~0.1s."""
    bucket = TokenBucket(rate_per_second=10, burst=3)
    for _ in range(3):
        bucket.acquire()
    start = time.monotonic()
    bucket.acquire()
    elapsed = time.monotonic() - start
    assert 0.05 < elapsed < 0.2  # ~0.1s expected, generous bounds


def test_bucket_does_not_exceed_capacity():
    """Idle time does not accumulate more than `burst` tokens."""
    bucket = TokenBucket(rate_per_second=100, burst=2)
    time.sleep(0.2)  # would give 20 tokens at this rate if uncapped
    # 2 immediate, 3rd must wait.
    bucket.acquire()
    bucket.acquire()
    start = time.monotonic()
    bucket.acquire()
    elapsed = time.monotonic() - start
    assert elapsed > 0.005


def test_invalid_config_raises():
    with pytest.raises(ValueError):
        TokenBucket(rate_per_second=0, burst=1)
    with pytest.raises(ValueError):
        TokenBucket(rate_per_second=1, burst=0)


def test_oversized_request_raises():
    bucket = TokenBucket(rate_per_second=1, burst=1)
    with pytest.raises(ValueError):
        bucket.acquire(tokens=5)
