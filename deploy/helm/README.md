# Helm charts

Kubernetes packaging for the Golden platform. The main chart is **`golden/`**.
The others are supporting infrastructure, or legacy per-service charts kept
for compatibility.

Every chart passes `helm lint --strict` and `helm template | kubeconform -strict`
under its default values, every `ci/*.yaml` file and every `values-*.yaml`
overlay. CI runs this through `scripts/ci/validate-infra.sh`.

## `golden/`: the platform chart

A single chart deploys every Python service from one image,
`ghcr.io/here2serveu/golden-platform`. Each service starts with
`golden serve <name>`:

| Service | Port | Domain |
| --- | --- | --- |
| api | 8000 | platform |
| transaction-engine | 8090 | fintech |
| fraud-detector | 8091 | fintech |
| payment-gateway | 8092 | fintech |
| ehr-ingestion | 8093 | healthcare |
| clinical-decision | 8094 | healthcare |
| patient-gateway | 8095 | healthcare |
| gpu-optimizer | 8096 | AI infrastructure (GPU) |
| migration-planner | 8097 | VMware to OpenShift migration |

For each entry in `services:`, the chart renders the following. `defaults:`
is deep-merged into every entry, so you only override what differs:

- a Deployment and a ClusterIP Service. Liveness/startup probes use `GET /health`, readiness uses `GET /ready`, and the pods carry Prometheus `prometheus.io/*` annotations for `GET /metrics`.
- hardened pods: `runAsNonRoot`, UID/GID 10001, `readOnlyRootFilesystem`, all capabilities dropped, `seccompProfile: RuntimeDefault`, and a writable `/tmp` emptyDir.
- optional HorizontalPodAutoscaler (`autoscaling.enabled`) and PodDisruptionBudget (on by default).
- optional PersistentVolumeClaim (`persistence.enabled`), using the chart-wide `storageClass`.

Release-wide objects:

- a ConfigMap with `GOLDEN_AUTONOMY_MODE` (`dry_run` | `supervised` | `autonomous`, default `dry_run`), `GOLDEN_KILL_SWITCH` and `GOLDEN_LOG_LEVEL`. It's injected with `envFrom`.
- a Secret reference for `GOLDEN_API_KEYS` (`apiKeys.existingSecret`). The chart creates the Secret only when `apiKeys.create=true`, which is for dev only.
- a ServiceAccount; set workload identity with `serviceAccount.annotations`.
- a NetworkPolicy that allows traffic within the release and from `networkPolicy.allowedNamespaces`, with optional egress lockdown.
- optional Ingress (`ingress.enabled`), OpenShift Routes (`route.enabled`) and a Prometheus Operator ServiceMonitor.

GPU: set `gpu.enabled=true`, or `services.gpu-optimizer.gpu.enabled=true`.
gpu-optimizer then requests `nvidia.com/gpu`, gets the
`nvidia.com/gpu.present=true` nodeSelector, and tolerates the
`nvidia.com/gpu` taint that the Terraform GPU node pools apply.

Images resolve as `<image.registry>/<image.name>:<image.tag>`. The defaults
are `ghcr.io/here2serveu`, `golden-platform` and the chart appVersion. Set
`image.repository` to override the full path.

### Cloud overlays

| File | Target | What it sets |
| --- | --- | --- |
| `values-aws.yaml` | EKS | ALB Ingress (`alb` class + annotations), `gp3`, IRSA `eks.amazonaws.com/role-arn` |
| `values-azure.yaml` | AKS | App routing Ingress (`webapprouting.kubernetes.azure.com`), `managed-csi`, `azure.workload.identity/client-id` + pod label `azure.workload.identity/use` |
| `values-gcp.yaml` | GKE | `gce` Ingress, `standard-rwo`, `iam.gke.io/gcp-service-account` |
| `values-openshift.yaml` | OpenShift / ROSA / ARO / OSD | Routes instead of Ingress; no fixed UID, so it's compatible with the restricted-v2 SCC |
| `values-local.yaml` | kind / minikube | 1 replica, no HPA/PDB/NetworkPolicy, dev API key |

More OpenShift overrides live in `deploy/openshift/helm-values/`. They cover
per-domain installs and the fixed-UID `golden-scc` variant.

### Deploy

```bash
# Terraform landing zone + kubeconfig + helm, in one step
scripts/deploy.sh aws dev            # or: azure|gcp <dev|staging|prod> [plan|apply|destroy]
scripts/deploy.sh openshift dev      # current `oc login`
scripts/deploy.sh local dev          # kind
scripts/deploy.sh gcp prod plan --dry-run   # print the commands only

# or plain Helm
helm upgrade --install golden deploy/helm/golden -n golden --create-namespace \
  -f deploy/helm/golden/values-aws.yaml \
  --set image.registry=<registry_url> --set image.tag=<tag> \
  --set-string 'serviceAccount.annotations.eks\.amazonaws\.com/role-arn=<role-arn>'
```

For GitOps, use `deploy/gitops/argocd/app-golden.yaml` or the Flux
`golden-helmrelease.yaml`.

## Supporting charts

| Chart | Purpose |
| --- | --- |
| `express-app/` | Golden-path chart for the Node.js apps. Defaults to `golden-workload` (port 8080); `ci/client-portal-values.yaml` covers `golden-client-portal` (3001). |
| `backstage/` | Backstage developer portal. Needs an external PostgreSQL; the password comes from a Secret. The Bitnami sub-chart was removed. |
| `redis/` | Isolated Celery worker pool (`ai-worker-isolated`) using a Redis broker from `deploy/terraform/modules/redis`. |
| `kafka-zookeeper/` | Kafka + ZooKeeper event backbone (dev/test). |
| `monitoring-stack/` | Prometheus + Grafana. |
| `otel-collector/` | OpenTelemetry Collector. |
| `splunk-forwarder/`, `splunk-hec/` | Splunk log shipping. |
| `kong-gateway/` | Kong API gateway. |
| `service-mesh/` | Istio Gateway/VirtualService and Linkerd ServiceProfile. Needs those CRDs, which kubeconform skips. |

## Deprecated per-service charts

`fraud-detection/`, `payment-gateway/`, `ehr-service/` and `clinical-gateway/`
each deploy one service. They follow the same contract (golden image,
`golden serve <name>`, `/health` and `/ready` probes, UID 10001) but are
marked `deprecated: true`. Use `golden/` instead.
