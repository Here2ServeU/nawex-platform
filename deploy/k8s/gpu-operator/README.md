# NVIDIA GPU Operator

Manifests for the GPU node stack the platform's GPU workloads (vLLM, Triton, training) and GPU
telemetry (`golden.gpu`, DCGM exporter) depend on.

| File | What |
|---|---|
| `namespace.yaml` | `gpu-operator` namespace (Pod Security privileged — node agents) |
| `clusterpolicy.yaml` | `ClusterPolicy`: driver, toolkit, device plugin, GFD, **MIG strategy mixed**, MIG manager, **DCGM exporter** + ServiceMonitor |
| `time-slicing-config.yaml` | Device-plugin sharing configs: `any` (**time-slicing, replicas: 4**), `mps`, `mig-shared` |
| `mig-config.yaml` | MIG manager layouts: `all-disabled`, `all-1g.10gb`, `all-3g.40gb`, `inference-mixed`, `half-mig` |

Background, decision table and cost math: [`docs/verticals/gpu-partitioning.md`](../../../docs/verticals/gpu-partitioning.md).

## Install (Helm, pinned)

```bash
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia && helm repo update

kubectl apply -f deploy/k8s/gpu-operator/namespace.yaml
kubectl apply -f deploy/k8s/gpu-operator/time-slicing-config.yaml
kubectl apply -f deploy/k8s/gpu-operator/mig-config.yaml

helm upgrade --install gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator \
  --version v24.9.0 \
  --set driver.enabled=true \
  --set mig.strategy=mixed \
  --set migManager.config.name=custom-mig-config \
  --set devicePlugin.config.name=time-slicing-config \
  --set devicePlugin.config.default=any \
  --set dcgmExporter.serviceMonitor.enabled=true \
  --wait
```

The chart renders the `ClusterPolicy` from these values; `clusterpolicy.yaml` is the same
configuration written out for review and GitOps — after the chart is installed, `kubectl apply -f
deploy/k8s/gpu-operator/clusterpolicy.yaml` reconciles it to exactly this spec. On EKS/GKE/AKS GPU
node images that already ship the driver, set `driver.enabled=false`. Pin the chart version and
upgrade deliberately: the operator rolls new drivers onto every GPU node.

Verify:

```bash
kubectl -n gpu-operator get pods                      # all Running / Completed (validator)
kubectl get nodes -L nvidia.com/gpu.product -L nvidia.com/mig.capable -L nvidia.com/mig.config.state
kubectl describe node <gpu-node> | grep -A8 Allocatable   # nvidia.com/gpu: 4 per GPU with time-slicing
```

## Partition a node with MIG

```bash
# 1. pick a layout from mig-config.yaml
kubectl label node gpu-node-1 nvidia.com/mig.config=inference-mixed --overwrite
# 2. the MIG manager drains GPU pods on the node, repartitions, then reports:
kubectl get node gpu-node-1 -o jsonpath='{.metadata.labels.nvidia\.com/mig\.config\.state}'   # success
# 3. resources appear as (mixed strategy):
kubectl get node gpu-node-1 -o jsonpath='{.status.allocatable}' | jq 'with_entries(select(.key|startswith("nvidia.com/mig")))'
#   {"nvidia.com/mig-1g.10gb":"2","nvidia.com/mig-2g.20gb":"1","nvidia.com/mig-3g.40gb":"1"}  (per GPU)
```

Pods then request a slice instead of a GPU:

```yaml
resources:
  limits:
    nvidia.com/mig-3g.40gb: 1
```

Pick a layout from workload requirements with the planner (`golden.gpu.partitioning`):

```python
from golden.gpu.partitioning import Workload, plan_partitioning
plan = plan_partitioning([Workload("fraud-onnx", 30, 0.4, isolation_required=True), ...], "H100-80GB",
                         price_per_gpu_hour=6.0)
plan.to_dict()   # per-GPU MIG layout, strategy per workload, GPUs and $ saved
```

## Switch a node to time-slicing or MPS

```bash
kubectl label node gpu-node-2 nvidia.com/mig.config=all-disabled --overwrite   # MIG off
kubectl label node gpu-node-2 nvidia.com/device-plugin.config=any --overwrite  # time-slicing x4
kubectl label node gpu-node-3 nvidia.com/device-plugin.config=mps --overwrite  # MPS x4
```

With time-slicing every replica is a full view of the GPU — there is no memory limit per pod, so
size workloads so their combined memory fits. Pods on time-sliced GPUs should belong to one team.

## Metrics

DCGM exporter publishes `DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_FB_USED`, `DCGM_FI_DEV_GPU_TEMP`,
`DCGM_FI_DEV_POWER_USAGE`, `DCGM_FI_DEV_XID_ERRORS` and, per MIG instance,
`DCGM_FI_PROF_GR_ENGINE_ACTIVE` (labelled `GPU_I_PROFILE`, `GPU_I_ID`). These feed the GPU optimizer
(`golden serve gpu-optimizer`) and the alerts in `docs/verticals/gpu.md`.
