from __future__ import annotations

import pytest

_PLATFORM_ENV = [
    "GOLDEN_AUTONOMY_MODE",
    "GOLDEN_KILL_SWITCH",
    "GOLDEN_KILL_SWITCH_FILE",
    "GOLDEN_API_KEYS",
    "GOLDEN_MAX_ACTIONS_PER_HOUR",
    "GOLDEN_MODEL_MANIFEST",
    "GOLDEN_MODEL_DIR",
    "GOLDEN_AUDIT_LOG",
    "GOLDEN_DEVICE",
    "GOLDEN_CHAOS_ENABLED",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Every test starts from safe defaults: dry_run, kill switch off, auth off, no trained models."""
    for name in _PLATFORM_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GOLDEN_MODEL_DIR", str(tmp_path / "no-models"))
    monkeypatch.setenv("GOLDEN_RATE_LIMIT_PER_MINUTE", "100000")
    monkeypatch.setenv("NO_COLOR", "1")


@pytest.fixture
def governor():
    from golden.security import ActionGovernor, AuditLog

    return ActionGovernor(audit=AuditLog(), max_actions_per_hour=10, max_per_action_per_hour=3, max_targets=3)
