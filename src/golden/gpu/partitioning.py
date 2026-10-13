"""GPU sharing planner: MIG profile packing, sharing-strategy recommendations and cost savings.

Four ways to put work on an NVIDIA data-centre GPU:

* **whole GPU**     — one pod owns the device. Large training, anything needing > a 4g slice.
* **MIG**           — Multi-Instance GPU (A100/H100/H200/B200/A30): hardware partitions with their own
  SMs, L2 and memory controllers. Fault and QoS isolation; fixed profile sizes.
* **time-slicing**  — the device plugin advertises N replicas of one GPU; contexts are time-multiplexed.
  No memory or fault isolation, but zero waste for bursty, mostly-idle inference and notebooks.
* **MPS**           — Multi-Process Service: kernels from several processes run concurrently with a
  compute-share limit per client. Best throughput for cooperating, same-tenant processes; a fault in
  one client can take down the others, so never across tenants.

MIG model (per NVIDIA's MIG user guide): an A100/H100 has **7 compute slices** and **8 memory
slices**. Each profile ``<c>g.<m>gb`` uses ``c`` compute slices and a fixed run of memory slices that
may only start at specific positions (e.g. ``3g`` at slice 0 or 4, ``4g`` only at 0). A layout is
valid when instances do not overlap, total compute is <= 7 and each profile's count is within its
maximum — :func:`valid_layout` checks this with the real placement table, so combinations such as
``3g + 3g + 1g`` (9 memory slices) are rejected. Profile memory is the nominal size in the name.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

COMPUTE_SLICES = 7
MEMORY_SLICES = 8
HOURS_PER_MONTH = 730
TIME_SLICING_REPLICAS = 4  # matches deploy/k8s/gpu-operator/time-slicing-config.yaml
MPS_MAX_CLIENTS = 48

WHOLE_GPU = "whole-gpu"
MIG = "mig"
TIME_SLICING = "time-slicing"
MPS = "mps"
STRATEGIES = (WHOLE_GPU, MIG, TIME_SLICING, MPS)


@dataclass(frozen=True)
class MigProfile:
    name: str
    compute_slices: int
    memory_slices: int
    memory_gb: float
    starts: tuple[int, ...]  # memory-slice positions the instance may start at

    @property
    def max_instances(self) -> int:
        return len(self.starts)

    @property
    def compute_fraction(self) -> float:
        return self.compute_slices / COMPUTE_SLICES


@dataclass(frozen=True)
class GPUModel:
    name: str
    memory_gb: float
    profiles: tuple[MigProfile, ...]

    def profile(self, name: str) -> MigProfile:
        for p in self.profiles:
            if p.name == name:
                return p
        raise KeyError(f"{self.name} has no MIG profile {name!r}")


def _profiles(unit_gb: int) -> tuple[MigProfile, ...]:
    """The A100/H100 profile family; ``unit_gb`` is the memory of one slice (5 or 10 GB)."""
    u = unit_gb
    return (
        MigProfile(f"1g.{u}gb", 1, 1, u, (0, 1, 2, 3, 4, 5, 6)),
        MigProfile(f"1g.{2 * u}gb", 1, 2, 2 * u, (0, 2, 4, 6)),
        MigProfile(f"2g.{2 * u}gb", 2, 2, 2 * u, (0, 2, 4)),
        MigProfile(f"3g.{4 * u}gb", 3, 4, 4 * u, (0, 4)),
        MigProfile(f"4g.{4 * u}gb", 4, 4, 4 * u, (0,)),
        MigProfile(f"7g.{8 * u}gb", 7, 8, 8 * u, (0,)),
    )


GPU_MODELS: dict[str, GPUModel] = {
    "A100-40GB": GPUModel("A100-40GB", 40, _profiles(5)),
    "A100-80GB": GPUModel("A100-80GB", 80, _profiles(10)),
    "H100-80GB": GPUModel("H100-80GB", 80, _profiles(10)),
}


def gpu_model(name: str) -> GPUModel:
    try:
        return GPU_MODELS[name]
    except KeyError:
        raise KeyError(f"unknown GPU model {name!r}; known: {sorted(GPU_MODELS)}") from None


# ------------------------------------------------------------------------------- MIG layouts
def valid_layout(gpu: GPUModel, profiles: Sequence[MigProfile | str]) -> list[tuple[str, int]] | None:
    """Return a placement ``[(profile, start_slice), ...]`` for these instances, or ``None``.

    Backtracking over the legal start positions (largest instances first); at most 7 instances with
    <= 7 starts each, so this is instant.
    """
    profs = [gpu.profile(p) if isinstance(p, str) else p for p in profiles]
    if sum(p.compute_slices for p in profs) > COMPUTE_SLICES:
        return None
    if sum(p.memory_slices for p in profs) > MEMORY_SLICES:
        return None
    counts = Counter(p.name for p in profs)
    if any(counts[p.name] > p.max_instances for p in profs):
        return None
    order = sorted(profs, key=lambda p: (-p.memory_slices, -p.compute_slices, p.name))
    used = [False] * MEMORY_SLICES
    placed: list[tuple[str, int]] = []

    def place(i: int) -> bool:
        if i == len(order):
            return True
        p = order[i]
        for s in p.starts:
            span = range(s, s + p.memory_slices)
            if s + p.memory_slices <= MEMORY_SLICES and not any(used[k] for k in span):
                for k in span:
                    used[k] = True
                placed.append((p.name, s))
                if place(i + 1):
                    return True
                placed.pop()
                for k in span:
                    used[k] = False
        return False

    return sorted(placed, key=lambda x: x[1]) if place(0) else None


# --------------------------------------------------------------------------------- workloads
@dataclass(frozen=True)
class Workload:
    name: str
    memory_gb: float
    compute_fraction: float  # share of a full GPU's SMs needed at peak, (0, 1]
    isolation_required: bool = False  # multi-tenant, regulated data or a hard latency SLO
    kind: str = "inference"  # inference | training | notebook | batch
    bursty: bool = False
    throughput_oriented: bool = False
    tenant: str = "default"

    def __post_init__(self) -> None:
        if self.memory_gb <= 0:
            raise ValueError(f"{self.name}: memory_gb must be positive")
        if not 0 < self.compute_fraction <= 1:
            raise ValueError(f"{self.name}: compute_fraction must be in (0, 1]")


@dataclass(frozen=True)
class Recommendation:
    workload: str
    strategy: str
    reason: str
    mig_profile: str | None = None


def smallest_profile(gpu: GPUModel, workload: Workload) -> MigProfile | None:
    """Smallest MIG profile with enough memory and compute; ``None`` if only a whole GPU will do."""
    fits = [
        p
        for p in gpu.profiles
        if p.memory_gb >= workload.memory_gb and p.compute_fraction + 1e-9 >= workload.compute_fraction
    ]
    if not fits:
        return None
    return min(fits, key=lambda p: (p.memory_slices, p.compute_slices))


def recommend_strategy(workload: Workload, gpu: GPUModel | str = "A100-80GB") -> Recommendation:
    """Rules, in priority order:

    1. needs more than the largest partition, or large training  -> whole GPU
    2. isolation / QoS required                                     -> MIG (smallest fitting profile)
    3. same-tenant, throughput-oriented                             -> MPS
    4. bursty small inference, or notebooks                         -> time-slicing
    5. otherwise (steady, small)                                    -> MIG (guaranteed slice, no waste)
    """
    g = gpu_model(gpu) if isinstance(gpu, str) else gpu
    w = workload
    profile = smallest_profile(g, w)
    large_training = w.kind == "training" and (w.compute_fraction >= 0.5 or w.memory_gb > g.memory_gb / 2)
    if profile is None or profile.compute_slices == COMPUTE_SLICES or large_training:
        why = "large training job" if large_training else "needs (nearly) the full device"
        return Recommendation(w.name, WHOLE_GPU, f"{why}: give it the whole GPU")
    if w.isolation_required:
        return Recommendation(
            w.name, MIG, "isolation/QoS required: MIG gives dedicated SMs, L2 and memory", profile.name
        )
    if w.throughput_oriented:
        return Recommendation(
            w.name, MPS, "same-tenant throughput work: MPS runs kernels concurrently with a compute cap"
        )
    if w.bursty or w.kind == "notebook":
        return Recommendation(
            w.name, TIME_SLICING, "bursty / mostly idle and no isolation need: time-slice a shared GPU"
        )
    return Recommendation(
        w.name,
        MIG,
        "steady small workload: a right-sized MIG slice avoids stranding a full GPU",
        profile.name,
    )


# ----------------------------------------------------------------------------------- planner
@dataclass
class PlannedGPU:
    index: int
    strategy: str
    workloads: list[str] = field(default_factory=list)
    mig_layout: list[tuple[str, int]] = field(default_factory=list)
    memory_gb_used: float = 0.0
    compute_used: float = 0.0
    tenant: str | None = None


@dataclass
class PartitionPlan:
    gpu_model: str
    gpus: list[PlannedGPU]
    recommendations: list[Recommendation]
    baseline_gpus: int
    price_per_gpu_hour: float

    @property
    def gpus_needed(self) -> int:
        return len(self.gpus)

    @property
    def gpus_saved(self) -> int:
        return max(self.baseline_gpus - self.gpus_needed, 0)

    @property
    def monthly_savings_usd(self) -> float:
        return round(self.gpus_saved * self.price_per_gpu_hour * HOURS_PER_MONTH, 2)

    @property
    def annual_savings_usd(self) -> float:
        return round(self.monthly_savings_usd * 12, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gpu_model": self.gpu_model,
            "baseline_gpus": self.baseline_gpus,
            "gpus_needed": self.gpus_needed,
            "gpus_saved": self.gpus_saved,
            "price_per_gpu_hour": self.price_per_gpu_hour,
            "monthly_savings_usd": self.monthly_savings_usd,
            "annual_savings_usd": self.annual_savings_usd,
            "gpus": [asdict(g) for g in self.gpus],
            "recommendations": [asdict(r) for r in self.recommendations],
        }


def pack_mig(gpu: GPUModel, profiles: Sequence[tuple[str, MigProfile]]) -> list[list[tuple[str, MigProfile]]]:
    """First-fit decreasing of ``(workload, profile)`` pairs onto MIG GPUs; each bin is a valid layout."""
    order = sorted(profiles, key=lambda wp: (-wp[1].memory_slices, -wp[1].compute_slices, wp[0]))
    bins: list[list[tuple[str, MigProfile]]] = []
    for item in order:
        for b in bins:
            if valid_layout(gpu, [p for _, p in b] + [item[1]]) is not None:
                b.append(item)
                break
        else:
            if valid_layout(gpu, [item[1]]) is None:
                raise ValueError(f"profile {item[1].name} cannot be placed on {gpu.name}")
            bins.append([item])
    return bins


def _pack_shared(gpu: GPUModel, items: Sequence[Workload], *, strategy: str, start: int) -> list[PlannedGPU]:
    """FFD for time-slicing / MPS: memory always sums (no partitioning); MPS also caps compute at 1.0
    and clients at 48; time-slicing caps replicas. GPUs are never shared across tenants."""
    cap = TIME_SLICING_REPLICAS if strategy == TIME_SLICING else MPS_MAX_CLIENTS
    out: list[PlannedGPU] = []
    for w in sorted(items, key=lambda w: (-w.memory_gb, -w.compute_fraction, w.name)):
        for g in out:
            fits = (
                g.tenant == w.tenant
                and len(g.workloads) < cap
                and g.memory_gb_used + w.memory_gb <= gpu.memory_gb
                and (strategy != MPS or g.compute_used + w.compute_fraction <= 1.0 + 1e-9)
            )
            if fits:
                g.workloads.append(w.name)
                g.memory_gb_used += w.memory_gb
                g.compute_used += w.compute_fraction
                break
        else:
            out.append(
                PlannedGPU(
                    start + len(out), strategy, [w.name], [], w.memory_gb, w.compute_fraction, w.tenant
                )
            )
    return out


def plan_partitioning(
    workloads: Sequence[Workload],
    gpu: GPUModel | str = "A100-80GB",
    *,
    price_per_gpu_hour: float = 4.0,
    strategies: dict[str, str] | None = None,
) -> PartitionPlan:
    """Recommend a strategy per workload, pack each strategy's workloads onto as few GPUs as possible
    and compare against the status quo of one whole GPU (or more, by memory) per workload.

    ``strategies`` overrides the recommendation per workload name.
    """
    g = gpu_model(gpu) if isinstance(gpu, str) else gpu
    names = [w.name for w in workloads]
    if len(set(names)) != len(names):
        raise ValueError("workload names must be unique")
    recs = [recommend_strategy(w, g) for w in workloads]
    for i, w in enumerate(workloads):
        forced = (strategies or {}).get(w.name)
        if forced:
            if forced not in STRATEGIES:
                raise ValueError(f"unknown strategy {forced!r}")
            prof = smallest_profile(g, w)
            if forced == MIG and prof is None:
                raise ValueError(f"{w.name} does not fit any MIG profile on {g.name}")
            recs[i] = Recommendation(
                w.name, forced, "operator override", prof.name if forced == MIG and prof else None
            )
    by_strategy: dict[str, list[Workload]] = {s: [] for s in STRATEGIES}
    for w, r in zip(workloads, recs, strict=True):
        by_strategy[r.strategy].append(w)

    gpus: list[PlannedGPU] = []
    for w in by_strategy[WHOLE_GPU]:
        for _ in range(max(1, math.ceil(w.memory_gb / g.memory_gb))):
            gpus.append(
                PlannedGPU(len(gpus), WHOLE_GPU, [w.name], [], min(w.memory_gb, g.memory_gb), 1.0, w.tenant)
            )
    rec_by_name = {r.workload: r for r in recs}
    mig_items = [(w.name, g.profile(rec_by_name[w.name].mig_profile or "")) for w in by_strategy[MIG]]
    for b in pack_mig(g, mig_items):
        layout = valid_layout(g, [p for _, p in b]) or []
        gpus.append(
            PlannedGPU(
                len(gpus),
                MIG,
                [n for n, _ in b],
                layout,
                sum(p.memory_gb for _, p in b),
                sum(p.compute_slices for _, p in b) / COMPUTE_SLICES,
            )
        )
    for strategy in (MPS, TIME_SLICING):
        gpus.extend(_pack_shared(g, by_strategy[strategy], strategy=strategy, start=len(gpus)))
    baseline = sum(max(1, math.ceil(w.memory_gb / g.memory_gb)) for w in workloads)
    return PartitionPlan(g.name, gpus, recs, baseline, price_per_gpu_hour)


def mig_lower_bound(gpu: GPUModel, profiles: Sequence[MigProfile | str]) -> int:
    """No packing can use fewer GPUs than this (compute- and memory-slice volume bounds)."""
    profs = [gpu.profile(p) if isinstance(p, str) else p for p in profiles]
    if not profs:
        return 0
    return max(
        math.ceil(sum(p.compute_slices for p in profs) / COMPUTE_SLICES),
        math.ceil(sum(p.memory_slices for p in profs) / MEMORY_SLICES),
    )
