"""Load ``platform.yaml`` (merged with an optional git-ignored ``platform.local.yaml``)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "project": {"name": "golden", "display_name": "Golden Platform", "owner": "platform-team"},
    "cloud": {"provider": "local", "region": "us-east-1", "environment": "dev", "gpu_node_pool": False},
    "image": {"registry": "ghcr.io/here2serveu", "tag": "latest"},
    "domains": ["healthcare", "fintech", "gpu", "migration", "identity"],
    "ai_safety": {
        "autonomy_mode": "dry_run",
        "max_actions_per_hour": 20,
        "rate_limit_per_minute": 600,
        "kill_switch": False,
    },
    "migration": {},
    "identity": {},
}
CLOUDS = {"aws", "azure", "gcp", "openshift", "local"}
DOMAINS = {"healthcare", "fintech", "gpu", "migration", "identity"}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        out[key] = (
            _merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
        )
    return out


def load(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else Path(os.getenv("GOLDEN_PLATFORM_CONFIG", "platform.yaml"))
    config = dict(DEFAULTS)
    for candidate in (path, path.with_name("platform.local.yaml")):
        if candidate.exists():
            config = _merge(config, yaml.safe_load(candidate.read_text(encoding="utf-8")) or {})
    validate(config)
    return config


def validate(config: dict[str, Any]) -> None:
    provider = config["cloud"]["provider"]
    if provider not in CLOUDS:
        raise ValueError(f"cloud.provider must be one of {sorted(CLOUDS)}, got {provider!r}")
    unknown = set(config["domains"]) - DOMAINS
    if unknown:
        raise ValueError(f"unknown domains {sorted(unknown)}; valid: {sorted(DOMAINS)}")
    if config["ai_safety"]["autonomy_mode"] not in {"dry_run", "supervised", "autonomous"}:
        raise ValueError("ai_safety.autonomy_mode must be dry_run, supervised or autonomous")


def get(key: str, config: dict[str, Any] | None = None) -> Any:
    """Dotted lookup, e.g. ``get("cloud.provider")``."""
    node: Any = config or load()
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(key)
        node = node[part]
    return node
