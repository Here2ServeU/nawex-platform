"""Thread-safe token-bucket rate limiter keyed by caller identity."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    def __init__(self, per_minute: int, burst: int | None = None, max_keys: int = 10_000) -> None:
        self.rate = max(per_minute, 1) / 60.0
        self.capacity = float(burst if burst is not None else max(per_minute, 1))
        self.max_keys = max_keys
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self.max_keys:  # bound memory under key-spraying abuse
                    self._buckets.clear()
                bucket = self._buckets[key] = _Bucket(self.capacity, now)
            bucket.tokens = min(self.capacity, bucket.tokens + (now - bucket.updated) * self.rate)
            bucket.updated = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True
            return False
