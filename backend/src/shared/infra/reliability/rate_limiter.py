# SPDX-License-Identifier: Apache-2.0
"""Token-bucket rate limiter."""
import time
import threading
from dataclasses import dataclass


@dataclass
class RateLimitConfig:
    requests_per_minute: int = 60
    tokens_per_minute: int = 100_000


class RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, config: RateLimitConfig):
        self._config = config
        self._tokens = float(config.requests_per_minute)
        self._max_tokens = float(config.requests_per_minute)
        self._refill_rate = config.requests_per_minute / 60.0  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> None:
        """Block until the requested number of tokens are available."""
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
            time.sleep(0.1)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now
