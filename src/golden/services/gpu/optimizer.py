"""GPU optimizer service — fleet anomaly detection, rightsizing and governed remediation plans."""

from __future__ import annotations

import os

from fastapi import Query
from prometheus_client import Gauge
from pydantic import BaseModel, Field

from golden.ai.accel import device_report
from golden.ai.agents.planner import PlannerAgent
from golden.gpu import GPUSample, analyze_fleet, collect_local, make_gpu_fleet
from golden.services.common import create_app, run

SERVICE = "gpu-optimizer"
GPU_UTIL = Gauge("golden_gpu_utilization_ratio", "GPU utilisation (0-1).", ["gpu", "node"])
GPU_TEMP = Gauge("golden_gpu_temperature_celsius", "GPU temperature.", ["gpu", "node"])
IDLE_GPUS = Gauge("golden_gpu_idle_gpus", "GPUs idle beyond the reclamation window.")
SAVINGS = Gauge("golden_gpu_projected_monthly_savings_usd", "Projected monthly savings from optimisation.")

app = create_app(SERVICE, "GPU / AI-infrastructure fleet optimisation.")
_planner = PlannerAgent()
_MAX_EXPORTED_SERIES = 2_000


class GPUSampleIn(BaseModel):
    node: str = Field(..., max_length=128)
    index: int = Field(..., ge=0, le=64)
    model: str = Field("unknown", max_length=128)
    utilization_pct: float = Field(..., ge=0, le=100)
    memory_used_pct: float = Field(0, ge=0, le=100)
    memory_total_gb: float = Field(0, ge=0, le=1024)
    temperature_c: float = Field(0, ge=0, le=130)
    power_w: float = Field(0, ge=0, le=2000)
    power_limit_w: float = Field(0, ge=0, le=2000)
    ecc_errors: int = Field(0, ge=0)
    xid_errors: int = Field(0, ge=0)
    idle_minutes: float = Field(0, ge=0)
    workload: str | None = Field(None, max_length=128)


class AnalyzeRequest(BaseModel):
    samples: list[GPUSampleIn] = Field(..., max_length=50_000)
    on_prem: bool = False


def _report(samples: list[GPUSample], on_prem: bool) -> dict:
    report = analyze_fleet(samples, on_prem=on_prem)
    for s in samples[:_MAX_EXPORTED_SERIES]:
        GPU_UTIL.labels(gpu=s.gpu_id, node=s.node).set(s.utilization_pct / 100)
        GPU_TEMP.labels(gpu=s.gpu_id, node=s.node).set(s.temperature_c)
    IDLE_GPUS.set(report.idle_gpus)
    SAVINGS.set(report.projected_annual_savings_usd / 12)
    plan = _planner.plan(
        {"status": "risk_detected" if report.risk_flags else "healthy", "risk_flags": report.risk_flags}
    )
    return {"report": report.to_dict(), "remediation_plan": plan}


@app.post("/api/v1/gpu/analyze")
def analyze(body: AnalyzeRequest) -> dict:
    return _report([GPUSample(**s.model_dump()) for s in body.samples], body.on_prem)


@app.get("/api/v1/gpu/fleet")
def simulated_fleet(
    scenario: str = Query("typical", pattern="^(typical|hot|efficient)$"),
    nodes: int = Query(8, ge=1, le=256),
    gpus_per_node: int = Query(8, ge=1, le=16),
) -> dict:
    return _report(make_gpu_fleet(nodes, gpus_per_node, scenario=scenario), on_prem=False)


@app.get("/api/v1/gpu/local")
def local() -> dict:
    samples = collect_local()
    return {"gpus": [s.to_dict() for s in samples], **(_report(samples, True) if samples else {})}


@app.get("/api/v1/gpu/accelerator")
def accelerator() -> dict:
    return device_report()


def main() -> None:
    run(app, int(os.getenv("PORT", "8096")))


if __name__ == "__main__":
    main()
