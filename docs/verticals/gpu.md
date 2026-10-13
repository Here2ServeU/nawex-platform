# GPU / AI-Infrastructure Domain

## Problem

GPUs are now the most expensive line item in most AI-heavy cloud bills, yet fleet-wide
utilization is often reported in the 20–40 % range [needs source]. Teams over-request whole accelerators for notebooks and
small inference services, jobs finish and leave GPUs allocated, thermals and ECC errors
degrade hardware silently, and nobody owns the bill end to end. The GPU domain applies the
same observe → detect → decide → act loop the platform uses for healthcare and fintech to
**GPU / AI-infrastructure fleets**: on-prem DGX/HGX clusters, Kubernetes/OpenShift GPU node
pools and cloud GPU instances.

Code: `src/golden/gpu/` (domain logic), `src/golden/services/gpu/` (service
`golden serve gpu-optimizer`, port **8096**, `POST /api/v1/gpu/analyze`).

## Signals

| Signal | Source | Platform metric |
|---|---|---|
| SM utilization | DCGM `DCGM_FI_DEV_GPU_UTIL`, `nvidia-smi` | `golden_gpu_utilization_ratio{gpu,node}` |
| Temperature | `DCGM_FI_DEV_GPU_TEMP` | `golden_gpu_temperature_celsius{gpu,node}` |
| Framebuffer memory used | `DCGM_FI_DEV_FB_USED` | (analysis input) |
| Power draw | `DCGM_FI_DEV_POWER_USAGE` | (analysis input) |
| XID / ECC errors | `DCGM_FI_DEV_XID_ERRORS`, ECC counters | alert `GPUXidErrors` |
| Allocation | Kubernetes `nvidia.com/gpu` requests, MIG profiles, scheduler | `golden_gpu_idle_gpus` |
| Price | on-demand / reserved / spot price per GPU-hour | `golden_gpu_projected_monthly_savings_usd` |

## Detections

- **Thermal anomaly** — sustained > 85 °C (alert `GPUThermalHigh`, 5 m) or a device running hot
  relative to its peers at the same load (cooling / airflow fault).
- **Memory anomaly** — framebuffer near full with low SM activity (leak / oversized batch), or
  memory fragmentation causing OOM retries.
- **ECC / XID faults** — XID 48/63/64/79/94/95 indicate double-bit ECC, row-remap and
  fallen-off-the-bus faults: cordon and drain.
- **Idle GPUs** — allocated but < 5 % utilization for ≥ 30 min (`GPUIdleFleetHigh`).
- **Chronic under-utilization** — < 20 % for ≥ 1 h (`GPUUnderutilized`).
- **Stragglers** — one rank of a distributed job far slower than its peers (NVLink/PCIe or thermal).

Anomaly scoring reuses `golden.ai.anomaly_detection`; all telemetry passes the input guardrails
(`golden.security.guardrails`) before scoring.

## Optimizations

| Optimization | When | Action (governor risk) |
|---|---|---|
| **Rightsizing** | Workload never exceeds a fraction of the device | Move to a smaller SKU / fractional GPU — `migrate_gpu_workload` (high) |
| **Consolidation / bin-packing** | Many lightly loaded GPUs across nodes | Pack workloads onto fewer GPUs/nodes and release the rest — `consolidate_gpu_workloads` (high) |
| **MIG partitioning** | A100/H100 with several small inference services | Recommend MIG profiles (e.g. 1g.10gb, 3g.40gb) so one GPU serves up to 7 isolated tenants |
| **Power capping** | Memory-bound or latency-tolerant work | `nvidia-smi -pl` / DCGM power limits — energy saving vs throughput loss depends on the workload — measure per job [needs source for typical ranges] — `set_gpu_power_cap` (low) |
| **Spot / preemptible** | Checkpointed training, batch inference | Shift to spot capacity with checkpoint cadence sized to the interruption rate |
| **Idle reclamation** | Allocated but idle GPUs (notebooks, finished jobs) | Reclaim after a grace period — `reclaim_idle_gpus` (low) |
| **Drain faulty nodes** | XID/ECC faults | Cordon + drain — `drain_gpu_node` (high) |

All actions run through the action governor: in the default `dry_run` mode the optimizer only
produces recommendations; see [AI safety](../security/ai-safety.md).

## ROI framing

```bash
golden roi --vertical gpu --tier professional
golden demo client --vertical gpu --client "Acme AI" --fast
```

Savings model (per month):

```text
savings = Σ idle_reclaimed_gpu_hours × price_per_gpu_hour
        + Σ consolidated_gpus × hours × price
        + Σ (on_demand − spot) × eligible_hours
        + power_cap_kWh_saved × energy_price × PUE
```

Outcomes to quote come from the client's own telemetry, not from a typical-range claim. On the bundled
sample fleet, `golden gpu analyze --scenario hot` reports 64 GPUs at 43.5 % average utilization, 12 idle,
and 3 nodes freeable by consolidation (synthetic data). Re-run it on the client's DCGM export.
The headline number is exported as `golden_gpu_projected_monthly_savings_usd` and shown on the
**Golden Platform — GPU / AI Infrastructure** dashboard.

## Regulatory & operational alignment

- **FinOps Framework** — inform (per-team GPU cost allocation), optimize (rightsizing, spot,
  commitments), operate (budgets and alerts).
- **Sustainability reporting** — energy and carbon per training run (CSRD / SEC climate
  disclosures, GHG Protocol Scope 2).
- **EU AI Act / NIST AI RMF** — documented, monitored infrastructure for high-risk AI systems;
  audit trail of every automated infrastructure change (hash-chained audit log).
- **SOC 2 change management** — high-risk changes (consolidation, drains) require approval in
  `supervised` mode; every verdict is logged.
- **SRE** — thermal and XID alerts route to `#golden-gpu-alerts`; utilization SLOs are tracked
  in Grafana.

## Observability

- Prometheus job `gpu` (`gpu-optimizer:8096`) and optional `dcgm-exporter` (`dcgm-exporter:9400`,
  compose profile `gpu`).
- Rules: `observability/prometheus/rules/gpu_rules.yml`.
- Dashboard: `observability/grafana/dashboards/golden-gpu.json`.
- Training on GPUs: [guides/gpu-acceleration.md](../guides/gpu-acceleration.md).
