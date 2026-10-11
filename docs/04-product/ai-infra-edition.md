# AI Infrastructure (GPU) Edition

The AI Infrastructure Edition packages the platform's **GPU / AI-infrastructure domain** for
organizations running GPU fleets — on-prem DGX/HGX clusters, Kubernetes/OpenShift GPU node pools
and cloud GPU instances. Domain details: [verticals/gpu.md](../verticals/gpu.md).

## Who it is for

- AI platform / MLOps teams with ≥ 16 GPUs and no fleet-level utilization view
- FinOps teams whose GPU spend is the fastest-growing cloud line item
- Infrastructure / SRE teams responsible for GPU node health (thermals, ECC/XID faults)

## What is included

| Capability | Description |
|---|---|
| GPU telemetry ingestion | DCGM exporter, `nvidia-smi`, Kubernetes allocation (`nvidia.com/gpu`, MIG) |
| Anomaly detection | Thermal (> 85 °C sustained, peer outliers), memory, ECC/XID faults, stragglers |
| Optimization recommendations | Rightsizing, consolidation/bin-packing, MIG partitioning, power capping, spot/preemptible, idle reclamation |
| Governed automation | Power caps & idle reclamation (low risk); consolidation, migration, drains (high risk, approval in `supervised` mode) |
| Savings & ROI | `golden roi --vertical gpu --tier professional`; `golden_gpu_projected_monthly_savings_usd` |
| Dashboards & alerts | `golden-gpu.json`; `gpu_rules.yml` (thermal, idle, < 20 % utilization, XID) |
| GPU-accelerated training | AMP (bf16/fp16), TF32, `torch.compile` — [guides/gpu-acceleration.md](../guides/gpu-acceleration.md) |

## Service

`golden serve gpu-optimizer` (port **8096**) — `POST /api/v1/gpu/analyze` with fleet telemetry; returns
anomalies, recommendations and projected savings. Requires `X-API-Key` when `GOLDEN_API_KEYS` is set.

## Demo

```bash
golden demo client --vertical gpu --client "Acme AI" --fast
golden roi --vertical gpu --tier professional
```

## Tiers

| | Starter | Professional | Enterprise |
|---|---|---|---|
| GPUs monitored | up to 64 | up to 512 | unlimited, multi-cluster |
| Recommendations | ✓ | ✓ | ✓ |
| Governed automation | dry-run only | supervised | supervised / autonomous |
| MIG & power-cap planning | — | ✓ | ✓ |
| FinOps chargeback & sustainability reports | — | ✓ | ✓ |
| Dedicated SRE / TAM | — | — | ✓ |
