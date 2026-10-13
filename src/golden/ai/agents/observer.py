"""Observer agent — collects telemetry from a workload's JSON metrics endpoint or a simulator."""

from __future__ import annotations

import logging
import os
import random
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ObserverAgent:
    def __init__(self, config: dict[str, Any], rng: random.Random | None = None) -> None:
        obs = config.get("observability", {})
        self.source = os.getenv("GOLDEN_OBSERVER_SOURCE") or obs.get("source", "simulated")
        self.http_endpoint = os.getenv("GOLDEN_OBSERVER_ENDPOINT") or obs.get(
            "http_endpoint", "http://localhost:8080/metrics/json"
        )
        self.timeout = float(obs.get("http_timeout_seconds", 3))
        self.rng = rng or random.Random()

    def collect_metrics(self) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        try:
            if self.source == "http":
                response = httpx.get(self.http_endpoint, timeout=self.timeout)
                response.raise_for_status()
                payload = response.json()
                m = payload.get("metrics", payload)
                return {
                    "timestamp": payload.get("timestamp", now),
                    "source": "http",
                    "latency_ms": float(m.get("latency_ms", 0) or 0),
                    "error_rate_percent": float(m.get("error_rate", 0) or 0),
                    "cpu_usage_percent": float(m.get("cpu_usage_percent", 0) or 0),
                    "memory_usage_percent": float(m.get("memory_usage_percent", 0) or 0),
                }
            return {
                "timestamp": now,
                "source": "simulated",
                "latency_ms": round(190 + self.rng.uniform(-20, 40), 2),
                "error_rate_percent": round(self.rng.uniform(0, 0.5), 2),
                "cpu_usage_percent": round(self.rng.uniform(40, 75), 1),
                "memory_usage_percent": round(self.rng.uniform(30, 60), 1),
            }
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("metrics collection failed: %s", exc)
            return {"timestamp": now, "source": self.source, "status": "collection_failed", "error": str(exc)}
