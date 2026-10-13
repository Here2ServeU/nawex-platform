"""Clinical decision support — NEWS2 deterioration scoring and PHI access anomaly auditing."""

from __future__ import annotations

import os

from prometheus_client import Histogram
from pydantic import BaseModel, Field

from golden.ai.pipelines.clinical_risk import news2
from golden.ai.pipelines.detect_phi_anomalies import calculate_phi_risk_score
from golden.security.guardrails import VITALS_BOUNDS, check_bounds, clamp_score
from golden.services.common import create_app, run

SERVICE = "clinical-decision"
PHI_RISK = Histogram("golden_phi_risk_score", "PHI access risk scores.", buckets=[i / 10 for i in range(11)])

app = create_app(SERVICE, "NEWS2 clinical deterioration scoring and HIPAA PHI-access anomaly detection.")


class Vitals(BaseModel):
    event_id: str = Field("unknown", max_length=128)
    heart_rate: float
    spo2: float
    systolic_bp: float
    temperature: float
    respiratory_rate: float = 16
    on_supplemental_oxygen: bool = False
    consciousness: str = Field("alert", pattern="^(alert|confusion|voice|pain|unresponsive|cvpu)$")
    department: str = Field("general", max_length=64)


class PHIAccess(BaseModel):
    user_id: str = Field(..., max_length=128)
    role: str = Field("clinician", max_length=32)
    access_type: str = Field("read", max_length=32)
    record_count: int = Field(1, ge=0, le=1_000_000)
    is_after_hours: bool = False
    is_weekend: bool = False
    cross_department: bool = False


@app.post("/score")
def score_vitals(v: Vitals) -> dict:
    check_bounds(v.model_dump(), VITALS_BOUNDS)  # physiologically impossible input -> 422
    result = news2(
        respiratory_rate=v.respiratory_rate,
        spo2=v.spo2,
        systolic_bp=v.systolic_bp,
        heart_rate=v.heart_rate,
        temperature=v.temperature,
        on_supplemental_oxygen=v.on_supplemental_oxygen,
        consciousness=v.consciousness,
    )
    threshold = float(os.getenv("ANOMALY_THRESHOLD", "0.35"))  # NEWS2 >= 7 of 20
    return {
        "event_id": v.event_id,
        "news2": result.to_dict(),
        "anomaly_score": round(result.normalized, 4),
        "is_anomaly": result.normalized >= threshold,
        "risk_level": result.level,
        "model_version": "news2-rcp-2017",
    }


@app.post("/api/v1/phi/access-audit")
def phi_access_audit(event: PHIAccess) -> dict:
    risk = clamp_score(calculate_phi_risk_score(event.model_dump()))
    PHI_RISK.observe(risk)
    suspicious = risk >= float(os.getenv("PHI_RISK_THRESHOLD", "0.30"))
    return {
        "user_id": event.user_id,
        "risk_score": round(risk, 4),
        "is_suspicious": suspicious,
        "recommendation": "investigate" if suspicious else "allow",
    }


def main() -> None:
    run(app, int(os.getenv("PORT", "8094")))


if __name__ == "__main__":
    main()
