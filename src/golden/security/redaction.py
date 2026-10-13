"""PHI / PII redaction for logs, audit entries and model explanations."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEYS = frozenset(
    {
        "patient_id",
        "ssn",
        "dob",
        "date_of_birth",
        "mrn",
        "npi",
        "insurance_id",
        "card_number",
        "pan",
        "account_number",
        "password",
        "secret",
        "token",
        "api_key",
        "authorization",
    }
)

_FIELD_PATTERN = re.compile(
    r"(?i)\b(patient_id|ssn|dob|mrn|npi|insurance_id|card_number|account_number)\s*[:=]\s*[^\s,;]+"
)
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

REDACTED = "[REDACTED]"


def redact_text(text: str) -> str:
    text = _FIELD_PATTERN.sub(lambda m: f"{m.group(1)}={REDACTED}", text)
    text = _SSN.sub(REDACTED, text)
    text = _CARD.sub(REDACTED, text)
    return _EMAIL.sub(REDACTED, text)


def redact_obj(obj: Any) -> Any:
    """Recursively redact sensitive keys and free-text values in dicts/lists/strings."""
    if isinstance(obj, dict):
        return {k: (REDACTED if str(k).lower() in SENSITIVE_KEYS else redact_obj(v)) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj
