"""API-key authentication (constant-time comparison, keys from ``GOLDEN_API_KEYS``)."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable


def verify_api_key(provided: str | None, valid_keys: Iterable[str]) -> bool:
    if not provided:
        return False
    provided_b = provided.encode()
    matched = False
    for key in valid_keys:  # always walk every key so timing doesn't reveal which one matched
        matched |= hmac.compare_digest(provided_b, key.encode())
    return matched


def key_fingerprint(key: str) -> str:
    """Short non-reversible identifier for logs, rate-limit buckets and audit entries."""
    return hashlib.sha256(key.encode()).hexdigest()[:12]
