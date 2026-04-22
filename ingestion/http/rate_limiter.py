"""Token-bucket rate limiter.

A simple, thread-safe-enough-for-our-purposes implementation. Each call to
`acquire()` blocks until a token is available. Tokens regenerate at
`rate_per_second`; the bucket holds up to `burst` tokens at rest.

This is not a production-grade distributed rate limiter. For a single-process
pipeline hitting a few APIs it's exactly right.
"""

from __future__ import annotations

import threading
import time


class TokenBucket:
    def __init__(self, rate_per_second: float, burst: int):
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        if burst < 1:
            raise ValueError("burst must be at least 1")
        self.rate = rate_per_second
        self.capacity = burst
        self._tokens: float = float(burst)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Add tokens based on time elapsed since the last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    def acquire(self, tokens: int = 1) -> None:
        """Block until `tokens` are available, then consume them."""
        if tokens > self.capacity:
            raise ValueError(f"requested {tokens} tokens exceeds capacity {self.capacity}")
        with self._lock:
            while True:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                # Compute how long to sleep before enough tokens exist.
                deficit = tokens - self._tokens
                sleep_s = deficit / self.rate
                time.sleep(sleep_s)
