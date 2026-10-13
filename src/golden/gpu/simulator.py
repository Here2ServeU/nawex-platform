"""Synthetic GPU fleet telemetry for demos, tests and the client portal."""

from __future__ import annotations

import random

from golden.gpu.telemetry import GPUSample

_MODELS = [
    ("NVIDIA H100 80GB HBM3", 80.0, 700.0),
    ("NVIDIA A100-SXM4-80GB", 80.0, 400.0),
    ("NVIDIA L40S", 48.0, 350.0),
]
_JOBS = ["llm-finetune", "recsys-train", "fraud-inference", "imaging-inference", "notebook", None]


def make_gpu_fleet(
    n_nodes: int = 8,
    gpus_per_node: int = 8,
    *,
    scenario: str = "typical",
    seed: int | None = 42,
) -> list[GPUSample]:
    """Generate a fleet snapshot.

    Scenarios: ``typical`` (≈40% average utilisation, some idle GPUs), ``hot`` (a node thermally
    throttling plus a GPU reporting ECC errors), ``efficient`` (well-packed fleet).
    """
    rng = random.Random(seed)
    fleet: list[GPUSample] = []
    for n in range(n_nodes):
        node = f"gpu-node-{n + 1:02d}"
        model, mem_gb, tdp = _MODELS[n % len(_MODELS)]
        for i in range(gpus_per_node):
            job = rng.choice(_JOBS)
            if scenario == "efficient":
                util = rng.uniform(65, 92)
            elif job is None:
                util = rng.uniform(0, 3)
            elif job == "notebook":
                util = rng.uniform(2, 15)
            else:
                util = rng.uniform(25, 95)
            sample = GPUSample(
                node=node,
                index=i,
                model=model,
                uuid=f"GPU-{n:02d}{i:02d}-{rng.randrange(16**8):08x}",
                utilization_pct=round(util, 1),
                memory_used_pct=round(min(100.0, util * rng.uniform(0.6, 1.1) + (0 if job else 1)), 1),
                memory_total_gb=mem_gb,
                temperature_c=round(34 + util * 0.45 + rng.uniform(-3, 3), 1),
                power_w=round(tdp * (0.12 + 0.85 * util / 100), 1),
                power_limit_w=tdp,
                idle_minutes=round(rng.uniform(90, 600), 0) if job is None else 0.0,
                workload=job,
            )
            fleet.append(sample)

    if scenario == "hot" and fleet:
        for s in fleet:
            if s.node == "gpu-node-03":
                s.temperature_c = round(rng.uniform(88, 93), 1)
                s.utilization_pct = max(s.utilization_pct, 85.0)
        fleet[-1].ecc_errors = 4
        fleet[-1].xid_errors = 2
    return fleet
