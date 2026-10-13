"""Optimization recommendations: idle resources, rightsizing, commitments, Kubernetes cost allocation.

Every recommendation carries an estimated monthly saving and a confidence derived from how much
utilization history backs it (``high`` >= 14 days of hourly samples, ``medium`` >= 7 days, else ``low``)
and, for commitments, how steady the spend is. Savings assume linear pricing within an instance family
(halving vCPUs halves the price), which holds for the general-purpose families on all three clouds;
treat the numbers as sizing for a ticket, not as a quote.

Kubernetes allocation follows the OpenCost model: a node's hourly price is split into CPU and RAM by the
relative unit prices, each workload pays for ``max(request, usage)`` of each resource, and capacity no
workload claims is reported as ``__idle__`` (optionally shared back to namespaces).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

HOURS_PER_MONTH = 730.0
IDLE_CPU_PERCENT = 5.0
IDLE = "__idle__"
# OpenCost default on-demand unit prices (USD/hour); only their ratio matters for the CPU/RAM split.
CPU_HOURLY = 0.031611
RAM_GIB_HOURLY = 0.004237


@dataclass
class ResourceUtilization:
    resource_id: str
    resource_type: str
    hourly_cost: float
    vcpus: int
    cpu_percent: list[float]  # hourly samples, 0-100
    memory_percent: list[float] = field(default_factory=list)
    team: str = ""
    provider: str = "AWS"

    @property
    def monthly_cost(self) -> float:
        return self.hourly_cost * HOURS_PER_MONTH


@dataclass
class Recommendation:
    resource_id: str
    kind: str  # terminate-idle | rightsize | commitment
    action: str
    current_monthly_cost: float
    estimated_monthly_savings: float
    confidence: str  # high | medium | low
    evidence: dict[str, Any] = field(default_factory=dict)
    team: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def history_confidence(samples: int) -> str:
    if samples >= 14 * 24:
        return "high"
    if samples >= 7 * 24:
        return "medium"
    return "low"


def _percentile(values: Sequence[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), q)) if len(values) else 0.0


def _next_power_of_two(x: float) -> int:
    return 1 if x <= 1 else 2 ** math.ceil(math.log2(x))


def rightsizing(
    resources: Sequence[ResourceUtilization],
    *,
    idle_cpu_percent: float = IDLE_CPU_PERCENT,
    headroom: float = 0.25,
    min_savings: float = 10.0,
) -> list[Recommendation]:
    """Idle and over-provisioned compute.

    * idle: p95 CPU below ``idle_cpu_percent`` (and memory p95 below 20% when sampled) → stop/terminate,
      saving the whole cost;
    * rightsize: vCPUs needed = vcpus x max(p95 CPU, p95 memory) x (1 + ``headroom``), rounded up to the
      next instance size (power of two); recommended when that is smaller than today.
    """
    out: list[Recommendation] = []
    for r in resources:
        cpu_p95 = _percentile(r.cpu_percent, 95)
        mem_p95 = _percentile(r.memory_percent, 95) if r.memory_percent else 0.0
        samples = len(r.cpu_percent)
        evidence = {"cpu_p95": round(cpu_p95, 2), "memory_p95": round(mem_p95, 2), "samples": samples}
        if cpu_p95 < idle_cpu_percent and (not r.memory_percent or mem_p95 < 20.0):
            out.append(
                Recommendation(
                    resource_id=r.resource_id,
                    kind="terminate-idle",
                    action=f"stop or terminate {r.resource_type} (p95 CPU {cpu_p95:.1f}%)",
                    current_monthly_cost=round(r.monthly_cost, 2),
                    estimated_monthly_savings=round(r.monthly_cost, 2),
                    confidence=history_confidence(samples),
                    evidence=evidence,
                    team=r.team,
                )
            )
            continue
        utilization = max(cpu_p95, mem_p95) / 100.0
        target_vcpus = min(_next_power_of_two(r.vcpus * utilization * (1.0 + headroom)), r.vcpus)
        if target_vcpus >= r.vcpus:
            continue
        savings = r.monthly_cost * (1.0 - target_vcpus / r.vcpus)
        if savings < min_savings:
            continue
        out.append(
            Recommendation(
                resource_id=r.resource_id,
                kind="rightsize",
                action=f"resize {r.resource_type} from {r.vcpus} to {target_vcpus} vCPUs",
                current_monthly_cost=round(r.monthly_cost, 2),
                estimated_monthly_savings=round(savings, 2),
                confidence=history_confidence(samples),
                evidence={**evidence, "target_vcpus": target_vcpus, "headroom": headroom},
                team=r.team,
            )
        )
    return sorted(out, key=lambda x: x.estimated_monthly_savings, reverse=True)


def commitment_recommendation(
    hourly_spend: Sequence[float],
    *,
    discount: float = 0.28,
    current_commitment: float = 0.0,
    baseline_percentile: float = 10.0,
    product: str = "Compute Savings Plan (1yr, no upfront)",
) -> Recommendation | None:
    """Savings Plan / RI / CUD commitment sized to the steady baseline of on-demand-eligible spend.

    The baseline is the ``baseline_percentile`` (p10) of hourly spend: a commitment at that level is used
    ~90% of hours, so little of it is wasted. ``current_commitment`` (USD/hour already committed) is
    subtracted. Savings = new commitment x ``discount`` x hours/month. Confidence drops with short
    history or volatile spend (coefficient of variation > 0.5).
    """
    if not hourly_spend:
        return None
    spend = np.asarray(hourly_spend, dtype=float)
    baseline = float(np.percentile(spend, baseline_percentile))
    additional = max(baseline - current_commitment, 0.0)
    if additional <= 0:
        return None
    mean = float(spend.mean())
    cv = float(spend.std() / mean) if mean else 0.0
    confidence = history_confidence(len(spend))
    if cv > 0.5 and confidence == "high":
        confidence = "medium"
    elif cv > 0.5:
        confidence = "low"
    coverage_after = min((current_commitment + additional) / mean, 1.0) if mean else 0.0
    return Recommendation(
        resource_id="compute-spend",
        kind="commitment",
        action=f"commit ${additional:.2f}/hour more in a {product}",
        current_monthly_cost=round(mean * HOURS_PER_MONTH, 2),
        estimated_monthly_savings=round(additional * discount * HOURS_PER_MONTH, 2),
        confidence=confidence,
        evidence={
            "baseline_hourly": round(baseline, 4),
            "mean_hourly": round(mean, 4),
            "coefficient_of_variation": round(cv, 3),
            "current_commitment_hourly": current_commitment,
            "coverage_before": round(min(current_commitment / mean, 1.0), 4) if mean else 0.0,
            "coverage_after": round(coverage_after, 4),
            "discount": discount,
            "samples": len(spend),
        },
    )


# ----------------------------------------------------------------------------- kubernetes
@dataclass
class Node:
    name: str
    hourly_cost: float
    cpu_cores: float
    memory_gib: float


@dataclass
class Pod:
    namespace: str
    node: str
    cpu_request: float  # cores
    memory_request_gib: float
    cpu_usage: float = 0.0
    memory_usage_gib: float = 0.0
    name: str = ""


@dataclass
class ClusterAllocation:
    hourly: dict[str, float]  # namespace (and __idle__) -> USD/hour
    total_hourly: float
    idle_hourly: float

    @property
    def idle_ratio(self) -> float:
        return self.idle_hourly / self.total_hourly if self.total_hourly else 0.0

    def monthly(self) -> dict[str, float]:
        return {k: round(v * HOURS_PER_MONTH, 2) for k, v in self.hourly.items()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "hourly": {k: round(v, 4) for k, v in self.hourly.items()},
            "monthly": self.monthly(),
            "total_hourly": round(self.total_hourly, 4),
            "idle_ratio": round(self.idle_ratio, 4),
        }


def allocate_cluster_cost(
    nodes: Sequence[Node],
    pods: Sequence[Pod],
    *,
    share_idle: bool = False,
    cpu_hourly: float = CPU_HOURLY,
    ram_gib_hourly: float = RAM_GIB_HOURLY,
) -> ClusterAllocation:
    """OpenCost-style allocation of node cost to namespaces by ``max(request, usage)``.

    If workloads on a node claim more than its capacity, their claims are scaled down to capacity, so the
    node is never charged more than its price. Unclaimed capacity is ``__idle__``; ``share_idle=True``
    spreads it across namespaces in proportion to their allocated cost.
    """
    by_node: dict[str, list[Pod]] = {}
    for pod in pods:
        by_node.setdefault(pod.node, []).append(pod)

    hourly: dict[str, float] = {}
    idle = 0.0
    total = 0.0
    for node in nodes:
        total += node.hourly_cost
        cpu_weight = node.cpu_cores * cpu_hourly
        ram_weight = node.memory_gib * ram_gib_hourly
        cpu_share = cpu_weight / (cpu_weight + ram_weight) if cpu_weight + ram_weight else 0.5
        cpu_cost = node.hourly_cost * cpu_share
        ram_cost = node.hourly_cost - cpu_cost
        residents = by_node.get(node.name, [])
        cpu_claims = [max(p.cpu_request, p.cpu_usage) for p in residents]
        ram_claims = [max(p.memory_request_gib, p.memory_usage_gib) for p in residents]
        cpu_scale = min(1.0, node.cpu_cores / sum(cpu_claims)) if sum(cpu_claims) else 0.0
        ram_scale = min(1.0, node.memory_gib / sum(ram_claims)) if sum(ram_claims) else 0.0
        allocated = 0.0
        for pod, cpu, ram in zip(residents, cpu_claims, ram_claims, strict=True):
            cost = 0.0
            if node.cpu_cores:
                cost += cpu_cost * cpu * cpu_scale / node.cpu_cores
            if node.memory_gib:
                cost += ram_cost * ram * ram_scale / node.memory_gib
            hourly[pod.namespace] = hourly.get(pod.namespace, 0.0) + cost
            allocated += cost
        idle += max(node.hourly_cost - allocated, 0.0)

    if share_idle and hourly:
        assigned = sum(hourly.values())
        hourly = {ns: c + idle * c / assigned for ns, c in hourly.items()} if assigned else hourly
        idle_out = 0.0
    else:
        idle_out = idle
        if idle:
            hourly[IDLE] = idle
    ordered = dict(sorted(hourly.items(), key=lambda kv: kv[1], reverse=True))
    return ClusterAllocation(hourly=ordered, total_hourly=total, idle_hourly=idle_out)


# ----------------------------------------------------------------------------- sample data
def sample_utilization(seed: int = 11, hours: int = 14 * 24) -> list[ResourceUtilization]:
    """Four resources: idle, over-provisioned, well-sized, and memory-bound (no CPU-only downsizing)."""
    rng = np.random.default_rng(seed)

    def series(mean: float, sd: float) -> list[float]:
        return [float(x) for x in np.clip(rng.normal(mean, sd, hours), 0.0, 100.0)]

    return [
        ResourceUtilization("i-0orphan", "m6i.2xlarge", 0.384, 8, series(1.5, 0.6), series(6, 1), team=""),
        ResourceUtilization(
            "i-search-nodes", "m6i.4xlarge", 0.768, 16, series(14, 4), series(25, 4), team="search"
        ),
        ResourceUtilization(
            "i-payments-api", "c6i.2xlarge", 0.34, 8, series(62, 8), series(55, 5), team="payments"
        ),
        ResourceUtilization(
            "vm-etl-01", "Standard_E8s_v5", 0.504, 8, series(12, 3), series(82, 4), team="data-platform"
        ),
    ]


def sample_hourly_compute_spend(seed: int = 5, hours: int = 30 * 24) -> list[float]:
    """Hourly on-demand compute spend with a ~$40/h floor, business-hours peaks and noise."""
    rng = np.random.default_rng(seed)
    hour_of_day = np.arange(hours) % 24
    peak = np.where((hour_of_day >= 8) & (hour_of_day < 20), 25.0, 0.0)
    return [float(x) for x in 40.0 + peak + rng.normal(0.0, 3.0, hours)]


def sample_cluster() -> tuple[list[Node], list[Pod]]:
    """Two m6i.2xlarge-class nodes (8 vCPU / 32 GiB, $0.384/h) running three namespaces."""
    nodes = [Node("node-a", 0.384, 8, 32), Node("node-b", 0.384, 8, 32)]
    pods = [
        Pod("payments", "node-a", 2.0, 4.0, name="payments-api-1"),
        Pod("payments", "node-a", 2.0, 4.0, name="payments-api-2"),
        Pod("search", "node-a", 1.0, 8.0, name="search-1"),
        Pod("search", "node-b", 1.0, 8.0, cpu_usage=2.5, name="search-2"),
        Pod("monitoring", "node-b", 0.5, 2.0, name="prometheus-0"),
    ]
    return nodes, pods
