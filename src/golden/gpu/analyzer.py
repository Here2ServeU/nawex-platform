"""GPU fleet analysis: anomaly detection, optimisation recommendations and projected savings.

Detections
    thermal throttling risk, ECC/XID hardware errors, memory pressure with low compute (leak or
    fragmentation), idle GPUs, chronic under-utilisation.
Optimisations
    idle reclamation, consolidation via first-fit-decreasing bin-packing, MIG partitioning for small
    workloads on MIG-capable parts, power capping for memory-bound / low-SM jobs.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from golden.ai.business_value.impact_estimator import ImpactEstimator
from golden.gpu.telemetry import GPUSample
from golden.security.guardrails import GPU_BOUNDS, check_bounds, validate_batch_size

THERMAL_WARN_C = 85.0
THERMAL_CRIT_C = 90.0
IDLE_UTIL_PCT = 5.0
IDLE_MINUTES = 60.0
UNDERUTILIZED_PCT = 30.0
TARGET_PACKING_PCT = 70.0
MIG_CAPABLE = ("A100", "H100", "H200", "A30", "B200")


@dataclass
class Finding:
    gpu_id: str
    kind: str
    severity: str  # info | warning | critical
    message: str
    action: str | None = None


@dataclass
class FleetReport:
    gpus: int
    nodes: int
    avg_utilization_pct: float
    avg_memory_used_pct: float
    idle_gpus: int
    underutilized_gpus: int
    hot_gpus: int
    hardware_faults: int
    total_power_w: float
    nodes_freeable_by_consolidation: int
    findings: list[Finding] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    risk_flags: dict[str, str] = field(default_factory=dict)
    projected_annual_savings_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate(samples: Sequence[GPUSample]) -> None:
    validate_batch_size(len(samples), max_size=50_000)
    for s in samples:
        check_bounds(
            {
                "utilization_pct": s.utilization_pct,
                "memory_used_pct": s.memory_used_pct,
                "temperature_c": s.temperature_c,
                "power_w": s.power_w,
            },
            GPU_BOUNDS,
        )


def nodes_freeable(samples: Sequence[GPUSample], target_pct: float = TARGET_PACKING_PCT) -> int:
    """First-fit-decreasing: how many whole nodes could be emptied by repacking busy GPUs."""
    by_node: dict[str, list[GPUSample]] = defaultdict(list)
    for s in samples:
        by_node[s.node].append(s)
    if not by_node:
        return 0
    gpus_per_node = max(len(v) for v in by_node.values())
    loads = sorted((s.utilization_pct for s in samples if s.utilization_pct > IDLE_UTIL_PCT), reverse=True)
    bins: list[float] = []
    for load in loads:
        for i, used in enumerate(bins):
            if used + load <= target_pct:
                bins[i] += load
                break
        else:
            bins.append(load)
    nodes_needed = -(-len(bins) // gpus_per_node)  # ceil
    return max(len(by_node) - nodes_needed, 0)


def analyze_fleet(samples: Sequence[GPUSample], *, on_prem: bool = False) -> FleetReport:
    _validate(samples)
    if not samples:
        return FleetReport(0, 0, 0.0, 0.0, 0, 0, 0, 0, 0.0, 0)

    findings: list[Finding] = []
    idle, under, hot, faults = [], [], [], []
    for s in samples:
        if s.temperature_c >= THERMAL_WARN_C:
            sev = "critical" if s.temperature_c >= THERMAL_CRIT_C else "warning"
            hot.append(s)
            findings.append(
                Finding(
                    s.gpu_id,
                    "thermal",
                    sev,
                    f"{s.temperature_c:.0f}°C — clocks will throttle",
                    "migrate_gpu_workload",
                )
            )
        if s.ecc_errors or s.xid_errors:
            faults.append(s)
            findings.append(
                Finding(
                    s.gpu_id,
                    "hardware",
                    "critical",
                    f"{s.ecc_errors} uncorrected ECC / {s.xid_errors} XID errors",
                    "drain_gpu_node",
                )
            )
        if s.utilization_pct < IDLE_UTIL_PCT and s.idle_minutes >= IDLE_MINUTES:
            idle.append(s)
            findings.append(
                Finding(
                    s.gpu_id, "idle", "warning", f"idle for {s.idle_minutes:.0f} min", "reclaim_idle_gpus"
                )
            )
        elif s.utilization_pct < UNDERUTILIZED_PCT:
            under.append(s)
            if s.memory_used_pct >= 90:
                findings.append(
                    Finding(
                        s.gpu_id,
                        "memory_pressure",
                        "warning",
                        f"{s.memory_used_pct:.0f}% memory at {s.utilization_pct:.0f}% compute — "
                        "possible leak or fragmentation",
                        None,
                    )
                )
        if s.power_limit_w and s.power_w > 0.95 * s.power_limit_w:
            findings.append(
                Finding(s.gpu_id, "power", "info", "drawing >95% of power limit", "set_gpu_power_cap")
            )

    n = len(samples)
    avg_util = sum(s.utilization_pct for s in samples) / n
    freeable = nodes_freeable(samples)

    recommendations: list[dict[str, Any]] = []
    if idle:
        recommendations.append(
            {
                "action": "reclaim_idle_gpus",
                "targets": [s.gpu_id for s in idle][:5],
                "detail": f"{len(idle)} GPUs idle ≥{IDLE_MINUTES:.0f} min",
            }
        )
    if freeable:
        recommendations.append(
            {
                "action": "consolidate_gpu_workloads",
                "detail": f"bin-packing to {TARGET_PACKING_PCT:.0f}% frees {freeable} node(s)",
            }
        )
    mig = [s for s in under if any(m in s.model for m in MIG_CAPABLE) and s.memory_used_pct < 40]
    if mig:
        recommendations.append(
            {
                "action": "enable_mig_partitioning",
                "targets": [s.gpu_id for s in mig][:5],
                "detail": f"{len(mig)} small workloads fit MIG slices (advisory)",
            }
        )
    capped = [s for s in samples if 15 <= s.utilization_pct < 60 and s.power_limit_w]
    if capped:
        recommendations.append(
            {"action": "set_gpu_power_cap", "detail": f"cap {len(capped)} GPUs at 80% TDP"}
        )
    for s in hot:
        recommendations.append(
            {
                "action": "migrate_gpu_workload",
                "params": {"node": s.node},
                "targets": [s.gpu_id],
                "detail": f"move {s.workload or 'workload'} off {s.gpu_id}",
            }
        )

    risk: dict[str, str] = {}
    if any(s.temperature_c >= THERMAL_CRIT_C for s in hot):
        risk["gpu_thermal_risk"] = "critical"
    elif hot:
        risk["gpu_thermal_risk"] = "high"
    if faults:
        risk["gpu_hardware_risk"] = "critical"
    if idle:
        risk["gpu_idle_risk"] = "low"
    if avg_util < UNDERUTILIZED_PCT + 10 and freeable:
        risk["gpu_efficiency_risk"] = "high"

    target = max(avg_util / 100, TARGET_PACKING_PCT / 100)
    savings = ImpactEstimator("gpu").estimate_gpu_optimization_impact(
        fleet_gpus=n,
        current_utilization=max(avg_util / 100, 0.01),
        target_utilization=target,
        on_prem=on_prem,
    )["annual_savings_usd"]

    return FleetReport(
        gpus=n,
        nodes=len({s.node for s in samples}),
        avg_utilization_pct=round(avg_util, 1),
        avg_memory_used_pct=round(sum(s.memory_used_pct for s in samples) / n, 1),
        idle_gpus=len(idle),
        underutilized_gpus=len(under),
        hot_gpus=len(hot),
        hardware_faults=len(faults),
        total_power_w=round(sum(s.power_w for s in samples), 1),
        nodes_freeable_by_consolidation=freeable,
        findings=findings,
        recommendations=recommendations,
        risk_flags=risk,
        projected_annual_savings_usd=savings,
    )
