"""Progressive model delivery: feature flag, shadow, canary steps and blue/green — with rollback.

* **flag**     — ``enabled=False`` sends everything to the champion instantly (no deploy).
* **shadow**   — the challenger scores every request but the champion answers; disagreement is tracked.
* **canary**   — sticky, hash-based split by request key through ``steps`` (5 → 20 → 50 → 100%).
  :meth:`analyze` compares challenger vs champion error rate and p95 latency; :meth:`advance` only
  moves to the next step when the analysis passes, otherwise it rolls back to 0%.
* **blue/green** — :meth:`cutover` flips 100% at once; :meth:`rollback` flips back.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from prometheus_client import Counter

ROUTED = Counter(
    "golden_model_requests_total", "Model requests by version and role.", ["model", "version", "role"]
)
SHADOW_DISAGREE = Counter(
    "golden_model_shadow_disagreements_total", "Champion/challenger disagreements.", ["model"]
)

Predictor = Callable[[Any], float]


@dataclass
class RolloutState:
    mode: str = "canary"  # canary | shadow | bluegreen
    enabled: bool = True
    steps: tuple[int, ...] = (5, 20, 50, 100)
    step_index: int = -1  # -1 = 0% (not started)
    stats: dict[str, dict[str, list[float]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list))
    )

    @property
    def weight(self) -> int:
        return 0 if self.step_index < 0 else self.steps[self.step_index]


class ModelRouter:
    def __init__(
        self,
        name: str,
        champion: tuple[str, Predictor],
        challenger: tuple[str, Predictor],
        *,
        mode: str = "canary",
    ) -> None:
        self.name = name
        self.champion, self.challenger = champion, challenger
        self.state = RolloutState(mode=mode)

    def _bucket(self, key: str) -> int:
        return int(hashlib.sha256(f"{self.name}:{key}".encode()).hexdigest()[:8], 16) % 100

    def route(
        self, key: str, features: Any, *, latency_ms: float | None = None, error: bool = False
    ) -> dict[str, Any]:
        s = self.state
        use_challenger = s.enabled and s.mode != "shadow" and self._bucket(key) < s.weight
        version, fn = self.challenger if use_challenger else self.champion
        score = fn(features)
        role = "challenger" if use_challenger else "champion"
        ROUTED.labels(model=self.name, version=version, role=role).inc()
        out: dict[str, Any] = {"version": version, "role": role, "score": score}
        if s.enabled and s.mode == "shadow":
            shadow = self.challenger[1](features)
            if (shadow >= 0.5) != (score >= 0.5):
                SHADOW_DISAGREE.labels(model=self.name).inc()
                s.stats["challenger"]["disagree"].append(1.0)
            else:
                s.stats["challenger"]["disagree"].append(0.0)
            out["shadow_score"] = shadow
        if latency_ms is not None:
            s.stats[role]["latency_ms"].append(latency_ms)
        s.stats[role]["error"].append(1.0 if error else 0.0)
        return out

    def analyze(
        self, *, max_error_delta: float = 0.01, max_latency_ratio: float = 1.2, min_samples: int = 50
    ) -> dict[str, Any]:
        champ, chall = self.state.stats["champion"], self.state.stats["challenger"]
        if len(chall["error"]) < min_samples:
            return {"verdict": "insufficient_data", "samples": len(chall["error"])}
        err_c, err_n = float(np.mean(champ["error"] or [0])), float(np.mean(chall["error"]))
        p95_c = float(np.percentile(champ["latency_ms"], 95)) if champ["latency_ms"] else 0.0
        p95_n = float(np.percentile(chall["latency_ms"], 95)) if chall["latency_ms"] else 0.0
        ok = err_n <= err_c + max_error_delta and (p95_c == 0 or p95_n <= p95_c * max_latency_ratio)
        return {
            "verdict": "pass" if ok else "fail",
            "error_rate": {"champion": err_c, "challenger": err_n},
            "p95_ms": {"champion": p95_c, "challenger": p95_n},
            "samples": len(chall["error"]),
        }

    def advance(self, **analysis_kw: Any) -> dict[str, Any]:
        s = self.state
        if s.step_index >= 0:
            verdict = self.analyze(**analysis_kw)
            if verdict["verdict"] == "fail":
                self.rollback()
                return {"action": "rolled_back", "analysis": verdict, "weight": s.weight}
            if verdict["verdict"] == "insufficient_data":
                return {"action": "hold", "analysis": verdict, "weight": s.weight}
        s.step_index = min(s.step_index + 1, len(s.steps) - 1)
        s.stats = defaultdict(lambda: defaultdict(list))
        return {"action": "advanced", "weight": s.weight, "complete": s.weight == 100}

    def cutover(self) -> None:
        self.state.mode, self.state.step_index = "bluegreen", len(self.state.steps) - 1

    def rollback(self) -> None:
        self.state.step_index = -1

    def set_flag(self, enabled: bool) -> None:
        self.state.enabled = enabled
