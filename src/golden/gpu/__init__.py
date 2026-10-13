"""GPU / AI-infrastructure optimisation domain."""

from golden.gpu.analyzer import Finding, FleetReport, analyze_fleet, nodes_freeable
from golden.gpu.partitioning import (
    GPU_MODELS,
    PartitionPlan,
    Workload,
    plan_partitioning,
    recommend_strategy,
    valid_layout,
)
from golden.gpu.simulator import make_gpu_fleet
from golden.gpu.telemetry import GPUSample, collect_local, parse_nvidia_smi_csv

__all__ = [
    "GPU_MODELS",
    "PartitionPlan",
    "Workload",
    "plan_partitioning",
    "recommend_strategy",
    "valid_layout",
    "FleetReport",
    "Finding",
    "GPUSample",
    "analyze_fleet",
    "collect_local",
    "make_gpu_fleet",
    "nodes_freeable",
    "parse_nvidia_smi_csv",
]
