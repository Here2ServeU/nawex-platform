"""API-key authentication (constant-time comparison, keys from ``GOLDEN_API_KEYS``)."""

from __future__ import annotations

import hmac
from collections.abc import Sequence


def match_api_key(provided: str | None, valid_keys: Sequence[str]) -> int | None:
    """Return the index of the matching key, or ``None``.

    Every key is compared (constant time per key) so timing does not reveal which one matched. The index
    — never the key or a hash of it — identifies the caller for rate limiting and audit.
    """
    if not provided:
        return None
    provided_b = provided.encode()
    match: int | None = None
    for index, key in enumerate(valid_keys):
        if hmac.compare_digest(provided_b, key.encode()) and match is None:
            match = index
    return match


def verify_api_key(provided: str | None, valid_keys: Sequence[str]) -> bool:
    return match_api_key(provided, valid_keys) is not None
