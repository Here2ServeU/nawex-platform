"""National Early Warning Score 2 (NEWS2) — Royal College of Physicians, 2017.

Deterministic, published, and auditable: the right backbone for clinical deterioration alerts.
Clinical response bands: 0–4 low, 5–6 (or any single parameter scoring 3) medium, ≥7 high.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _rr(v: float) -> int:
    if v <= 8:
        return 3
    if v <= 11:
        return 1
    if v <= 20:
        return 0
    if v <= 24:
        return 2
    return 3


def _spo2_scale1(v: float) -> int:
    if v <= 91:
        return 3
    if v <= 93:
        return 2
    if v <= 95:
        return 1
    return 0


def _sbp(v: float) -> int:
    if v <= 90:
        return 3
    if v <= 100:
        return 2
    if v <= 110:
        return 1
    if v <= 219:
        return 0
    return 3


def _pulse(v: float) -> int:
    if v <= 40:
        return 3
    if v <= 50:
        return 1
    if v <= 90:
        return 0
    if v <= 110:
        return 1
    if v <= 130:
        return 2
    return 3


def _temp(v: float) -> int:
    if v <= 35.0:
        return 3
    if v <= 36.0:
        return 1
    if v <= 38.0:
        return 0
    if v <= 39.0:
        return 1
    return 2


@dataclass
class News2Result:
    score: int
    level: str
    components: dict[str, int] = field(default_factory=dict)
    recommendation: str = ""

    @property
    def normalized(self) -> float:
        return min(self.score / 20.0, 1.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "normalized": round(self.normalized, 4),
            "components": self.components,
            "recommendation": self.recommendation,
        }


def news2(
    *,
    respiratory_rate: float,
    spo2: float,
    systolic_bp: float,
    heart_rate: float,
    temperature: float,
    on_supplemental_oxygen: bool = False,
    consciousness: str = "alert",  # alert | cvpu (new confusion, voice, pain, unresponsive)
) -> News2Result:
    components = {
        "respiratory_rate": _rr(respiratory_rate),
        "spo2": _spo2_scale1(spo2),
        "supplemental_oxygen": 2 if on_supplemental_oxygen else 0,
        "systolic_bp": _sbp(systolic_bp),
        "pulse": _pulse(heart_rate),
        "consciousness": 0 if consciousness.lower() == "alert" else 3,
        "temperature": _temp(temperature),
    }
    total = sum(components.values())
    if total >= 7:
        level, rec = "high", "Emergency assessment by critical-care team; continuous monitoring"
    elif total >= 5 or 3 in components.values():
        level, rec = "medium", "Urgent clinician review; monitor at least hourly"
    else:
        level, rec = "low", "Routine monitoring (4–12 hourly)"
    return News2Result(total, level, components, rec)
