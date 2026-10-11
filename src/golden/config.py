"""Runtime settings, read from ``GOLDEN_*`` environment variables.

Settings are resolved on every call to :func:`get_settings` so tests and operators can flip a value
(for example the kill switch) without restarting the process.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum


class AutonomyMode(StrEnum):
    """How much the platform may act on its own.

    ``dry_run``    — plan and log only; nothing is executed (default, safest).
    ``supervised`` — low-risk actions execute; high-risk actions wait for human approval.
    ``autonomous`` — all allowed actions execute, still bounded by caps and the kill switch.
    """

    DRY_RUN = "dry_run"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_list(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    environment: str = "local"
    log_level: str = "INFO"
    log_json: bool = True
    autonomy_mode: AutonomyMode = AutonomyMode.DRY_RUN
    kill_switch: bool = False
    kill_switch_file: str = ""
    api_keys: tuple[str, ...] = field(default_factory=tuple)
    rate_limit_per_minute: int = 600
    max_actions_per_hour: int = 20
    max_body_bytes: int = 1_048_576
    model_dir: str = "models"
    model_manifest: str = ""
    audit_log_path: str = ""
    device: str = "auto"
    amp: bool = True
    compile: bool = False
    simulation_delay_seconds: float = 0.0

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_keys)


def get_settings() -> Settings:
    mode_raw = os.getenv("GOLDEN_AUTONOMY_MODE", AutonomyMode.DRY_RUN.value).strip().lower()
    try:
        mode = AutonomyMode(mode_raw)
    except ValueError:
        mode = AutonomyMode.DRY_RUN  # fail safe on a typo

    try:
        delay = float(os.getenv("GOLDEN_SIMULATION_DELAY_SECONDS", "0"))
    except ValueError:
        delay = 0.0

    return Settings(
        environment=os.getenv("GOLDEN_ENV", "local"),
        log_level=os.getenv("GOLDEN_LOG_LEVEL", "INFO").upper(),
        log_json=_env_bool("GOLDEN_LOG_JSON", True),
        autonomy_mode=mode,
        kill_switch=_env_bool("GOLDEN_KILL_SWITCH", False),
        kill_switch_file=os.getenv("GOLDEN_KILL_SWITCH_FILE", ""),
        api_keys=_env_list("GOLDEN_API_KEYS"),
        rate_limit_per_minute=_env_int("GOLDEN_RATE_LIMIT_PER_MINUTE", 600),
        max_actions_per_hour=_env_int("GOLDEN_MAX_ACTIONS_PER_HOUR", 20),
        max_body_bytes=_env_int("GOLDEN_MAX_BODY_BYTES", 1_048_576),
        model_dir=os.getenv("GOLDEN_MODEL_DIR", "models"),
        model_manifest=os.getenv("GOLDEN_MODEL_MANIFEST", ""),
        audit_log_path=os.getenv("GOLDEN_AUDIT_LOG", ""),
        device=os.getenv("GOLDEN_DEVICE", "auto").lower(),
        amp=_env_bool("GOLDEN_AMP", True),
        compile=_env_bool("GOLDEN_COMPILE", False),
        simulation_delay_seconds=max(0.0, delay),
    )
