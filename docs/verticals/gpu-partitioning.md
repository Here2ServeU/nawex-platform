# GPU Partitioning — whole GPU vs MIG vs time-slicing vs MPS

A Kubernetes pod that asks for `nvidia.com/gpu: 1` gets a whole accelerator, even when it is a 6 GB
inference model that keeps the SMs busy a few percent of the time. Sharing the device is the single
largest lever on GPU cost after reclaiming idle GPUs ([GPU domain](gpu.md)). There are four ways to
place work on an NVIDIA data-centre GPU; they differ in what they isolate.

Code: [`src/golden/gpu/partitioning.py`](../../src/golden/gpu/partitioning.py) ·
manifests: [`deploy/k8s/gpu-operator/`](../../deploy/k8s/gpu-operator/README.md) ·
tests: `tests/test_ml_platform.py`.

## The four strategies

| | Whole GPU | MIG (Multi-Instance GPU) | Time-slicing | MPS (Multi-Process Service) |
|---|---|---|---|---|
| How | One pod owns the device | Hardware partitions, each with its own SMs, L2 slice and memory controllers | Device plugin advertises N replicas; contexts take turns | Kernels from several processes run concurrently on shared SMs |
| Memory isolation | n/a | **Yes** (fixed per profile) | No — every replica sees all memory | Limit per client (configurable), not hardware-enforced like MIG |
| Fault isolation | n/a | **Yes** | No | No — one client's fatal fault can affect the others |
| Performance QoS | Full device | **Guaranteed** slice | None — noisy neighbours | Compute share cap per client |
| Granularity | 1 GPU | Fixed profiles (1/7 … 7/7) | Any N (here 4) | Any N (here 4), up to 48 clients |
| Hardware | Any | A100, A30, H100, H200, B200 | Any | Volta and newer |
| Reconfigure | — | Drain GPU pods on the node, repartition (MIG manager) | Change ConfigMap / node label | Change ConfigMap / node label |
| K8s resource | `nvidia.com/gpu` | `nvidia.com/mig-3g.40gb` (mixed strategy) | `nvidia.com/gpu` (replica) | `nvidia.com/gpu` (replica) |

## Decision table

`recommend_strategy()` applies these rules in order:

| # | Workload | Strategy | Why |
|---|---|---|---|
| 1 | Large training (≥ 50 % compute or > half the memory), or needs more than the largest partition | **Whole GPU** | Partitioning only adds overhead; NVLink/NCCL jobs want full devices |
| 2 | Isolation or QoS required — multi-tenant, regulated data (PHI/PCI), hard latency SLO | **MIG**, smallest fitting profile | Only MIG isolates memory, faults and performance in hardware |
| 3 | Same-tenant, throughput-oriented (batch embedding, offline scoring, many small workers) | **MPS** | Concurrent kernels fill the SMs better than taking turns |
| 4 | Bursty / mostly idle inference, notebooks, dev | **Time-slicing** | Zero waste when idle; acceptable because there is nothing to isolate |
| 5 | Steady small workload, no special need | **MIG** | A right-sized slice with guaranteed resources instead of a stranded GPU |

Never time-slice or MPS-share across tenants: neither isolates memory or faults. The planner only
co-locates time-sliced or MPS workloads with the same `tenant`.

## MIG profiles and placement

An A100/H100 has **7 compute slices** and **8 memory slices**. A profile `<c>g.<m>gb` takes `c`
compute slices and a fixed run of memory slices that may only **start at specific positions**:

| A100-40GB | A100-80GB / H100-80GB | Compute slices | Memory slices | Legal starts | Max per GPU |
|---|---|---|---|---|---|
| 1g.5gb | 1g.10gb | 1 | 1 | 0–6 | 7 |
| 1g.10gb | 1g.20gb | 1 | 2 | 0, 2, 4, 6 | 4 |
| 2g.10gb | 2g.20gb | 2 | 2 | 0, 2, 4 | 3 |
| 3g.20gb | 3g.40gb | 3 | 4 | 0, 4 | 2 |
| 4g.20gb | 4g.40gb | 4 | 4 | 0 | 1 |
| 7g.40gb | 7g.80gb | 7 | 8 | 0 | 1 |

So `4g + 3g` fits (slices 0–3 and 4–7), `3g + 2g + 1g + 1g` fits, but `3g + 3g + 1g` does not (nine
memory slices) and `4g + 4g` does not (a 4g instance can only start at slice 0). `valid_layout()`
checks a set of instances by backtracking over the legal starts, so the planner only emits layouts
the MIG manager can actually create. Profile memory is the nominal size in the name; usable memory
is slightly lower.

**Packing.** `pack_mig()` is first-fit decreasing: sort instances by memory slices then compute
slices, put each on the first GPU where the layout stays valid, open a new GPU otherwise. Tests check
it reaches the volume lower bound `max(⌈Σcompute/7⌉, ⌈Σmemory/8⌉)` on simple cases (seven 1g
instances → 1 GPU; `3g,4g,3g,4g` → 2; `3g,3g,1g` → 2).

## GPU Operator setup

The NVIDIA GPU Operator installs the driver, container toolkit, device plugin, GPU Feature
Discovery, MIG manager and DCGM exporter as DaemonSets. Platform configuration
([`deploy/k8s/gpu-operator/`](../../deploy/k8s/gpu-operator/README.md)):

* `clusterpolicy.yaml` — `mig.strategy: mixed` (each profile is its own resource), MIG manager with
  `custom-mig-config`, device plugin with `time-slicing-config`, DCGM exporter + ServiceMonitor.
* `time-slicing-config.yaml` — `any`: time-slicing with **replicas: 4**; `mps`: MPS ×4;
  `mig-shared`: time-slice MIG instances ×2.
* `mig-config.yaml` — layouts `all-1g.10gb`, `all-3g.40gb`, `inference-mixed`
  (`3g + 2g + 1g + 1g`), `half-mig`, `all-disabled`. A test checks every layout with `valid_layout`.

```bash
helm upgrade --install gpu-operator nvidia/gpu-operator -n gpu-operator --version v24.9.0 \
  --set mig.strategy=mixed --set migManager.config.name=custom-mig-config \
  --set devicePlugin.config.name=time-slicing-config --set devicePlugin.config.default=any
kubectl label node gpu-node-1 nvidia.com/mig.config=inference-mixed --overwrite      # MIG layout
kubectl label node gpu-node-2 nvidia.com/device-plugin.config=mps --overwrite        # MPS
```

Workloads then request what they were planned for — `nvidia.com/mig-3g.40gb: 1` (Triton in
`deploy/k8s/ml-serving/triton.yaml`) or `nvidia.com/gpu: 1` (vLLM on a whole GPU).

## Cost math

```
baseline_gpus = Σ_workloads max(1, ⌈memory_gb / gpu_memory_gb⌉)      # one GPU per pod today
gpus_needed   = whole-GPU GPUs + MIG GPUs (FFD) + MPS GPUs + time-sliced GPUs
gpus_saved    = baseline_gpus − gpus_needed
monthly $     = gpus_saved × price_per_gpu_hour × 730 h
```

Worked example on H100-80GB at an **assumed** $6.00 per GPU-hour (substitute your on-demand,
reserved or amortised on-prem rate):

| Workloads | Strategy | GPUs |
|---|---|---|
| 7 × fraud scorers (9 GB, 12 % compute, one per tenant, isolation) | MIG 1g.10gb | 2, shared with the Triton row: GPU A = 4 × 1g.10gb + 3g.40gb, GPU B = 3 × 1g.10gb |
| 1 × Triton ONNX (35 GB, 40 %, isolation) | MIG 3g.40gb | (in the 2 above) |
| 4 × chat endpoints (10 GB, 20 %, bursty) | time-slicing ×4 | 1 |
| embedding + rerank batch (30 + 20 GB, same team) | MPS | 1 |
| 1 × fine-tune (70 GB, 100 %) | whole GPU | 1 |
| **15 workloads** | | **5** (baseline 15) |

10 GPUs saved × $6.00 × 730 h = **$43,800 per month** ($525,600 per year) at the assumed price. The
same input reproduces this:

```python
from golden.gpu.partitioning import Workload, plan_partitioning

w = [Workload(f"fraud-{i}", 9, 0.12, isolation_required=True, tenant=f"t{i}") for i in range(7)]
w += [Workload(f"chat-{i}", 10, 0.2, bursty=True) for i in range(4)]
w += [Workload("embed-batch", 30, 0.4, throughput_oriented=True),
      Workload("rerank-batch", 20, 0.3, throughput_oriented=True),
      Workload("triton-onnx", 35, 0.4, isolation_required=True),
      Workload("finetune", 70, 1.0, kind="training")]
plan = plan_partitioning(w, "H100-80GB", price_per_gpu_hour=6.0)
plan.gpus_needed, plan.gpus_saved, plan.monthly_savings_usd   # (5, 10, 43800.0)
```

Caveats: the planner sizes by peak memory and compute share you supply — measure them (DCGM
`DCGM_FI_DEV_FB_USED`, `DCGM_FI_PROF_GR_ENGINE_ACTIVE`) rather than guessing. Time-slicing has no
memory limit, so co-located workloads must fit together; MIG reconfiguration drains the node's GPU
pods; and savings only materialise when the freed GPUs are released (node-pool scale-down or fewer
reserved instances).
