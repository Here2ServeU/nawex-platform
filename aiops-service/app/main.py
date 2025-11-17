from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import math

app = FastAPI(title="AIOps Demo API")

class PredictRequest(BaseModel):
  cpu: float
  memory: float
  latency_ms: Optional[float] = None

class PredictResponse(BaseModel):
  risk_score: float
  severity: str
  message: str

class FinOpsRequest(BaseModel):
  cpu_millicores: float
  memory_mb: float
  hours_per_month: float = 720
  node_hourly_price: float = 0.10  # simple demo value

class FinOpsResponse(BaseModel):
  estimated_monthly_cost: float
  recommendation: str


@app.get("/healthz")
def healthz():
  return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
  # Simple heuristic model for demo
  cpu_factor = req.cpu / 100.0
  mem_factor = req.memory / 100.0
  lat_factor = 0.0
  if req.latency_ms is not None:
    lat_factor = min(req.latency_ms / 1000.0, 2.0)

  risk_score = (0.5 * cpu_factor + 0.3 * mem_factor + 0.2 * lat_factor) * 100
  risk_score = min(max(risk_score, 0), 100)

  if risk_score < 40:
    severity = "low"
    message = "System is healthy."
  elif risk_score < 70:
    severity = "medium"
    message = "Monitor closely. Possible degradation."
  else:
    severity = "high"
    message = "High risk of incident. Consider scaling or investigating."

  return PredictResponse(
    risk_score=risk_score,
    severity=severity,
    message=message
  )


@app.post("/finops", response_model=FinOpsResponse)
def finops(req: FinOpsRequest):
  # Very simple estimation: usage % of a 1 vCPU / 1 GiB node
  cpu_capacity_m = 1000.0
  mem_capacity_mb = 1024.0

  cpu_ratio = req.cpu_millicores / cpu_capacity_m
  mem_ratio = req.memory_mb / mem_capacity_mb

  utilization = max(cpu_ratio, mem_ratio)
  utilization = min(max(utilization, 0.0), 1.0)

  # cost proportional to utilization
  monthly_cost = req.node_hourly_price * req.hours_per_month * utilization
  monthly_cost = round(monthly_cost, 2)

  if utilization < 0.3:
    recommendation = "Over-provisioned: consider using a smaller instance or reducing replicas."
  elif utilization < 0.7:
    recommendation = "Balanced: current resources are reasonable."
  else:
    recommendation = "Under-provisioned: consider scaling up or adding replicas."

  return FinOpsResponse(
    estimated_monthly_cost=monthly_cost,
    recommendation=recommendation
  )
