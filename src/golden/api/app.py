"""Platform API — the single front door for scoring, decisions, ROI and AI-safety operations."""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Literal

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field

from golden.ai.business_value import ROICalculator
from golden.ai.inference import aggregate_risk, run_all_predictors
from golden.ai.pipelines.clinical_risk import news2
from golden.ai.pipelines.detect_fraud import SIGNAL_WEIGHTS, fraud_signals
from golden.ai.pipelines.detect_phi_anomalies import calculate_phi_risk_score
from golden.decision import DecisionEngine, evaluate_risk
from golden.gpu import GPUSample, analyze_fleet
from golden.migration import VM, assess_inventory
from golden.security import clamp_score, default_governor, security_status, validate_sequence
from golden.security.guardrails import VITALS_BOUNDS, check_bounds
from golden.services.common import create_app, run

app = create_app("api", "Golden Platform API: risk scoring, governed decisions, ROI and AI-safety controls.")
engine = DecisionEngine()


# ----------------------------------------------------------------------------- models
class FraudIn(BaseModel):
    amount: float = Field(..., ge=0, le=10_000_000)
    channel: str = Field("online", max_length=32)
    country_code: str = Field("US", min_length=2, max_length=2)
    merchant_category_code: str = Field("0000", max_length=4)


class VitalsIn(BaseModel):
    heart_rate: float
    spo2: float
    systolic_bp: float
    temperature: float
    respiratory_rate: float = 16
    on_supplemental_oxygen: bool = False
    consciousness: str = Field("alert", pattern="^(alert|confusion|voice|pain|unresponsive|cvpu)$")


class PHIIn(BaseModel):
    role: str = Field("clinician", max_length=32)
    access_type: str = Field("read", max_length=32)
    record_count: int = Field(1, ge=0, le=1_000_000)
    is_after_hours: bool = False
    is_weekend: bool = False
    cross_department: bool = False


class ForecastIn(BaseModel):
    sequence: list[float] = Field(..., min_length=4, max_length=4096)


class SignalIn(BaseModel):
    """A telemetry/risk signal. Unknown keys are rejected so callers can't smuggle parameters."""

    model_config = {"extra": "forbid"}
    incident_class: str | None = Field(None, max_length=64)
    risk_score: float | None = Field(None, ge=0, le=1)
    fraud_score: float | None = Field(None, ge=0, le=1)
    phi_anomaly_score: float | None = Field(None, ge=0, le=1)
    clinical_risk_score: float | None = Field(None, ge=0, le=1)
    gpu_risk_score: float | None = Field(None, ge=0, le=1)
    latency_ms: float | None = Field(None, ge=0, le=600_000)
    slo_ms: float | None = Field(None, gt=0, le=600_000)
    error_rate_percent: float | None = Field(None, ge=0, le=100)
    gpu_temperature_c: float | None = Field(None, ge=0, le=130)
    gpu_utilization_pct: float | None = Field(None, ge=0, le=100)
    ecc_errors: int | None = Field(None, ge=0)
    xid_errors: int | None = Field(None, ge=0)
    migration_validation: Literal["passed", "failed"] | None = None
    criticality: Literal["low", "medium", "high", "mission_critical"] = "medium"
    target: str | None = Field(None, max_length=253)
    targets: list[str] | None = Field(None, max_length=100)
    node: str | None = Field(None, max_length=253)
    plan: str | None = Field(None, max_length=253)


class ApprovalIn(BaseModel):
    approver: str = Field(..., min_length=3, max_length=128)


# ----------------------------------------------------------------------------- scoring
@app.post("/v1/fraud/score", tags=["fintech"])
def fraud_score(body: FraudIn) -> dict:
    signals = fraud_signals(body.model_dump())
    score = clamp_score(sum(signals[k] * w for k, w in SIGNAL_WEIGHTS.items()))
    return {"fraud_score": round(score, 4), "risk_level": evaluate_risk(score), "signals": signals}


@app.post("/v1/clinical/news2", tags=["healthcare"])
def clinical_news2(body: VitalsIn) -> dict:
    check_bounds(body.model_dump(), VITALS_BOUNDS)
    return news2(**body.model_dump()).to_dict()


@app.post("/v1/phi/score", tags=["healthcare"])
def phi_score(body: PHIIn) -> dict:
    score = clamp_score(calculate_phi_risk_score(body.model_dump()))
    return {"phi_risk_score": round(score, 4), "risk_level": evaluate_risk(score)}


@app.post("/v1/reliability/forecast", tags=["reliability"])
def reliability_forecast(body: ForecastIn) -> dict:
    sequence = validate_sequence(body.sequence, min_length=4, low=0, high=600_000)
    scores = run_all_predictors(sequence, model_dir=os.getenv("GOLDEN_MODEL_DIR") or None)
    risk = aggregate_risk(scores)
    return {"scores": scores, "aggregate_risk": round(risk, 4), "risk_level": evaluate_risk(risk)}


@app.post("/v1/gpu/analyze", tags=["gpu"])
def gpu_analyze(samples: list[dict[str, Any]]) -> dict:
    if len(samples) > 50_000:
        raise HTTPException(status_code=422, detail="too many samples")
    try:
        parsed = [GPUSample(**s) for s in samples]
    except TypeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return analyze_fleet(parsed).to_dict()


@app.post("/v1/migration/assess", tags=["migration"])
def migration_assess(vms: list[dict[str, Any]]) -> dict:
    if not vms or len(vms) > 20_000:
        raise HTTPException(status_code=422, detail="provide between 1 and 20000 VMs")
    try:
        return assess_inventory([VM.from_dict(v) for v in vms])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid VM record: {exc}") from exc


# ----------------------------------------------------------------------------- decisions & ROI
@app.post("/v1/decisions", tags=["decisions"])
def decide(signal: SignalIn) -> dict:
    return engine.decide(signal.model_dump(exclude_none=True), actor="api").to_dict()


@app.get("/v1/decisions", tags=["decisions"])
def decisions(limit: int = Query(50, ge=1, le=1000)) -> dict:
    return {"decisions": [d.to_dict() for d in engine.history(limit)]}


@app.post("/v1/roi/{vertical}", tags=["business-value"])
def roi(
    vertical: Literal["healthcare", "fintech", "gpu", "migration"],
    tier: Literal["starter", "professional", "enterprise"] = "professional",
) -> dict:
    return ROICalculator.quick_summary(vertical, tier=tier)


# ----------------------------------------------------------------------------- AI safety
@app.get("/v1/security/status", tags=["ai-safety"])
def status() -> dict:
    return security_status()


@app.get("/v1/actions/pending", tags=["ai-safety"])
def pending() -> dict:
    return {"pending": [asdict(v) for v in default_governor().pending()]}


@app.post("/v1/actions/{request_id}/approve", tags=["ai-safety"])
def approve(request_id: str, body: ApprovalIn) -> dict:
    try:
        return asdict(default_governor().approve(request_id, body.approver))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/v1/actions/{request_id}/reject", tags=["ai-safety"])
def reject(request_id: str, body: ApprovalIn) -> dict:
    try:
        default_governor().reject(request_id, body.approver)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": request_id, "status": "rejected"}


@app.get("/v1/audit", tags=["ai-safety"])
def audit(limit: int = Query(100, ge=1, le=1000)) -> dict:
    log = default_governor().audit
    entries = log.entries()
    return {
        "chain_valid": log.verify(),
        "total": len(entries),
        "entries": [asdict(e) for e in entries[-limit:]],
    }


def main() -> None:
    run(app, int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    main()
