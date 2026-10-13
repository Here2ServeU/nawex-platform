# Platform engineering: delivery, scaling, secrets, DR, supply chain

This page covers the Kubernetes platform layer around the golden chart: how a release
reaches production, how capacity follows load, where secrets come from, how the cluster
is recovered, and how we know the image that runs is the one CI built.

Each optional feature is **off by default**. With default values the golden chart
renders exactly what it rendered before these features existed, so you can enable them
one at a time, per environment and per service.

| Concern | Chart values | Files |
|---|---|---|
| Progressive delivery | `rollouts.*`, `services.<n>.rollout.*` | `deploy/helm/golden/templates/deployment.yaml`, `analysistemplate.yaml`, `rollout-services.yaml` |
| Autoscaling | `services.<n>.autoscaling.*`, `services.<n>.keda.*` | `templates/hpa.yaml`, `templates/scaledobject.yaml`, `deploy/k8s/platform-addons/karpenter/` |
| Secrets | `externalSecrets.*`, `apiKeys.*` | `templates/externalsecret.yaml`, `deploy/k8s/platform-addons/external-secrets/` |
| Backup / DR | Terraform `velero_enabled` | `deploy/terraform/modules/aws/eks/velero.tf`, `deploy/k8s/platform-addons/velero/`, `ops/runbooks/playbooks/backup_restore_velero.md` |
| Node provisioning | Terraform `karpenter_enabled` | `deploy/terraform/modules/aws/eks/karpenter.tf`, `deploy/k8s/platform-addons/karpenter/` |
| Supply chain | - | `.github/workflows/containers.yml` (job `sign`), `security/policies/kyverno/` |
| DAST | - | `.github/workflows/dast.yml` |

The `deploy/helm/golden/ci/platform-addons-values.yaml` values file turns on Rollouts,
KEDA and External Secrets. `scripts/ci/validate-infra.sh` renders it with `helm lint
--strict` and `kubeconform`, so these code paths are validated on every change.

---

## 1. Progressive delivery

| Strategy | How it works | Blast radius of a bad release | Cost | When to use |
|---|---|---|---|---|
| **Rolling update** (Deployment default; golden uses `maxSurge: 1, maxUnavailable: 0`) | Replaces pods a few at a time. A pod gets traffic as soon as it is Ready. | Every user, once the rollout finishes. Readiness probes catch crashes, not wrong answers. | No extra capacity | Stateless services with good tests; non-critical paths |
| **Blue/green** | Runs a full new ReplicaSet next to the old one, then switches the Service selector in one step. | Every user at cutover. Rollback is instant (switch back). | 2x capacity during the release | Schema-coupled releases and cutovers that need an instant revert |
| **Canary** (implemented here) | Shifts traffic in weight steps. Metrics are checked between steps, and the rollout aborts on regression. | The canary weight (10% at first) for the analysis window | Small extra capacity | User-facing APIs with real traffic and good metrics |

**Implementation.** Set `rollouts.enabled: true`, then `services.<name>.rollout.enabled:
true` for each service. That service then renders an `argoproj.io/v1alpha1` **Rollout**
instead of a Deployment. Both are built from one helper (`golden.podTemplate` in
`_helpers.tpl`), so the pod spec cannot drift between the two kinds.

- **Steps** (`rollouts.canary.steps`, overridable per service): `setWeight 10 → pause 2m →
  25 → pause 2m → 50 → pause 5m → 100`.
- **Traffic split.** Without `trafficRouting`, Argo approximates weights by replica count,
  which is coarse at low replica counts. To split traffic precisely, set
  `services.<n>.rollout.trafficRouting` (for example `nginx.stableIngress`, `alb`, or
  `istio`). The chart then renders `<svc>-canary` and `<svc>-stable` Services and points
  the Ingress at the stable one.
- **Analysis** (`AnalysisTemplate <release>-canary`) runs in the background from step 1
  and queries Prometheus (`metrics.prometheusAddress`) every `rollouts.analysis.interval`:
  - *Success rate*: `golden_http_requests_total` with `status!~"5.."` divided by all
    requests. It must be ≥ `minSuccessRate` (default 0.99).
  - *p95 latency*: `histogram_quantile(0.95, golden_http_request_duration_seconds_bucket)`.
    It must be ≤ `maxP95LatencySeconds` (default 0.5).

  Probe and scrape paths (`/health`, `/ready`, `/metrics`) are excluded so they cannot
  dilute the error rate. With `selectCanaryPods: true`, queries filter on
  `rollouts_pod_template_hash`, so only the canary is judged. The chart adds that label
  to the ServiceMonitor `podTargetLabels` for you.
- **Abort.** When a metric fails more than `failureLimit` times, or errors more than
  `consecutiveErrorLimit` times (for example no data because the canary gets no
  traffic), Argo marks the rollout **Degraded/Aborted**. It then shifts all traffic back
  to stable and scales the canary down after `abortScaleDownDelaySeconds`. No human
  action is needed. To retry, fix the change and push a new revision. You can also run
  `kubectl argo rollouts retry rollout <name>`.
- **Scaling with Rollouts.** The HPA and the KEDA ScaledObject target `kind: Rollout`
  (via `golden.scaleTargetRef`), and `replicas` is not rendered when autoscaled.

Rollouts complement GitOps (`ops/runbooks/playbooks/deployment_rollback_gitops.md`).
Git still records what *should* run. The Rollout decides how fast it is allowed to
replace what *is* running.

## 2. Autoscaling layers

There are two layers. Pod autoscalers decide **how many pods** run. Node autoscalers
decide **how many machines** they run on.

| Layer | Signal | Reacts to | Notes |
|---|---|---|---|
| **HPA** (`autoscaling.enabled`) | CPU / memory utilisation (metrics-server) | Resource saturation | Lags behind I/O-bound or queue-driven load. Cannot scale to zero. |
| **KEDA** (`keda.enabled`) | Any external metric: Prometheus request rate (default), Kafka lag, cron, queue depth | Demand, before saturation | Creates and owns an HPA. The chart **disables its own HPA** for that service to avoid two controllers fighting. `minReplicaCount: 0` allows scale-to-zero for workers. |
| **Cluster Autoscaler** | Pending pods → grows a pre-defined node group (ASG) | Unschedulable pods | Only instance types already in the node group. Slower (ASG round-trip). |
| **Karpenter** (`karpenter_enabled`) | Pending pods → launches a right-sized instance directly (EC2 Fleet) | Unschedulable pods, under-utilised nodes | Chooses instance type, capacity type (spot/on-demand) and architecture per batch of pods. Consolidates nodes to cut cost. Handles spot interruptions via the SQS queue. |

The default KEDA trigger is `sum(rate(golden_http_requests_total{service=~"<name>|<k8s
svc>",...}[2m]))` against `requestsPerSecondThreshold` per replica. You can replace it with
`keda.query` or add triggers with `keda.extraTriggers`.

**Karpenter** is wired as follows in this repo:

- The EKS module keeps its managed `general` node group for the Karpenter controller and
  system add-ons. The controller is pinned off Karpenter nodes by node affinity.
- `karpenter.tf` adds the controller IRSA role (v1 policy), the node role and instance
  profile, an EKS access entry, and the SQS interruption queue with EventBridge rules.
  Every role carries `permissions_boundary_arn`.
- Subnets and the node security group get the `karpenter.sh/discovery=<name>` tag only
  when Karpenter is enabled.
- `deploy/k8s/platform-addons/karpenter/` defines an `EC2NodeClass` (AL2023, IMDSv2 with
  hop limit 1, encrypted gp3) and two NodePools:
  - `general`: spot and on-demand, c/m/r families gen 6+, consolidation, a 10%
    disruption budget, and CPU/memory limits.
  - `gpu`: on-demand g5/g6/p4d, tainted `nvidia.com/gpu=present:NoSchedule`, labelled
    `nvidia.com/gpu.present=true` to match the chart's GPU nodeSelector.

PodDisruptionBudgets (`podDisruptionBudget`) limit how much consolidation can disrupt
each service.

## 3. Secrets management

| Approach | Secret lands in | Rotation | Trade-offs |
|---|---|---|---|
| **External Secrets Operator** (implemented) | A native Kubernetes `Secret`, synced every `refreshInterval` | Change it in the backend; ESO updates the Secret within `refreshInterval`. | Works with `env`/`envFrom` and any controller. The value lives in etcd, so enable KMS envelope encryption. One controller covers many backends. |
| **Secrets Store CSI Driver** | A tmpfs volume in the pod (optionally mirrored to a Secret) | Remounted on rotation (if enabled). Env vars still need a restart. | Nothing in etcd unless you sync to a Secret. Per-pod mounts. The provider plugin must be on every node. |
| **Vault Agent injector** | A file rendered by a sidecar | Dynamic secrets with leases, renewed by the agent | Strongest model for short-lived database credentials. Needs Vault and a sidecar per pod, and ties apps to Vault. |

**Implementation.**

- In the chart, set `externalSecrets.enabled: true`. This renders one `ExternalSecret`
  (`external-secrets.io/v1beta1`, configurable through `externalSecrets.apiVersion`) per
  entry in `externalSecrets.secrets`.
- The `api-keys` entry targets the Secret that is already mounted as `GOLDEN_API_KEYS`
  (`apiKeys.existingSecret` or `<fullname>-api-keys`), so the workloads need no change.
  The chart refuses to render if `apiKeys.create=true` is also set, because two owners
  would fight over that Secret.
- `deploy/k8s/platform-addons/external-secrets/` has a `ClusterSecretStore` named
  `golden-secrets` for each backend: AWS Secrets Manager (IRSA), Azure Key Vault
  (workload identity), GCP Secret Manager (workload identity), and HashiCorp Vault
  (Kubernetes auth, pinned CA). Apply exactly one. Each store is restricted to the
  `golden` namespace by `conditions`.

**Rotation.** ESO updates the Secret. Because the services read `GOLDEN_API_KEYS` from an
env var, you need a rolling restart to pick up the new value. Either install Stakater
Reloader and annotate the workloads, or run `kubectl rollout restart`. `GOLDEN_API_KEYS`
accepts a comma-separated list, so you can rotate without downtime: add the new key,
roll out, move clients over, then remove the old key.

## 4. Backup and disaster recovery (Velero)

- **Terraform** (`velero_enabled = true`, `velero.tf`) creates:
  - A KMS key with rotation enabled.
  - An S3 bucket: versioned, SSE-KMS with a bucket key, all public access blocked,
    `BucketOwnerEnforced`, TLS-only bucket policy, and noncurrent-version expiry.
  - An IRSA role with a permission boundary, trusted only by `velero/velero-server`. Its
    policy grants only this bucket and this key. EC2 snapshot APIs are region-scoped, and
    `DeleteSnapshot` works only on snapshots tagged `velero.io/backup`.
  - The pinned Velero Helm release with the AWS plugin and no static credentials.
- **Schedules** (`deploy/k8s/platform-addons/velero/schedule-daily.yaml`):
  - Daily at 02:00 UTC for `golden` and `migrated-vms`, objects plus EBS snapshots, TTL 30
    days.
  - Hourly, objects only, TTL 72 h.
- **RPO / RTO:** 1 h for objects and 24 h for volume data. RTO is 60 min for a namespace
  restore, or 4 h when the cluster has to be rebuilt.
- These targets are only true if they are measured. The monthly drill in
  [backup_restore_velero.md](../../ops/runbooks/playbooks/backup_restore_velero.md)
  restores into a scratch namespace, checks `/health` and `/ready`, and records the real
  RPO and RTO.

Velero complements GitOps; it does not replace it. Git restores *manifests*. Velero
restores *state*: PV data, runtime-created objects, and the exact cluster snapshot.

## 5. Software supply-chain security

| Control | What it proves | Where |
|---|---|---|
| **SBOM** (SPDX) | What is inside the image (packages and versions) | BuildKit `sbom: true` in `containers.yml` (push step). `cosign attest --type spdxjson` signs it as an in-toto attestation. |
| **Provenance** | How, where and from which commit the image was built | BuildKit `provenance: true` (SLSA provenance attached to the image index) |
| **Signature** (keyless) | The image digest was produced by *this repo's* `containers.yml` on `main` or a `v*` tag | Job `sign`: Sigstore Fulcio certificate bound to the GitHub OIDC identity, logged in Rekor. `id-token: write` is granted only to this job, and it never runs for pull requests. |
| **Vulnerability scan** | No fixable CRITICAL CVEs at build time | Trivy step in `containers.yml` |
| **Admission verification** | Only signed, attested images from our identity run; tags are pinned to the verified digest | `security/policies/kyverno/verify-images.yaml` |
| **Baseline admission rules** | No `:latest`/untagged images; required labels | `disallow-latest-tag.yaml` (Enforce), `require-labels.yaml` (Audit). These mirror `security/policies/opa/k8s-security.rego`. |

**SLSA (Build track).**

- **L1** (provenance exists) is met.
- **L2** needs *signed* provenance from a hosted build platform. Hosted GitHub runners
  plus keyless-signed image and SBOM get most of the way. BuildKit's own provenance
  attestation, however, is not separately signed.
- **L3** needs hardened, isolated builds with non-forgeable provenance.

To claim L2/L3 for provenance itself, add `actions/attest-build-provenance` or the
`slsa-github-generator` reusable workflow, then verify with `cosign verify-attestation
--type slsaprovenance` or a Kyverno `attestations` rule.

The signing job uses cosign v2.x because Kyverno `verifyImages` reads the classic
`.sig`/`.att` tag layout. Revisit this when you adopt cosign v3 bundles (OCI referrers).

## 6. DAST vs SAST vs SCA

| | Looks at | Finds | Here |
|---|---|---|---|
| **SAST** | Source code, without running it | Injection patterns, unsafe APIs, path traversal, ReDoS | CodeQL (`security.yml`), ruff/mypy (`ci.yml`) |
| **SCA** | Dependencies and images | Known CVEs | Trivy image scan (`containers.yml`), Trivy filesystem scan of dependencies and IaC misconfigurations (`security.yml`); secrets via gitleaks (`security.yml`) |
| **DAST** | The running application over HTTP | Missing security headers, auth gaps, misconfigurations, injection that is actually reachable | OWASP ZAP (`dast.yml`) |

`dast.yml` runs weekly, on demand, and on PRs labelled `dast`. It:

1. Starts the API from `compose.yaml` (`api` on :8000) in dry-run mode with the kill
   switch on.
2. Waits for `/health`.
3. Runs a ZAP **baseline** (passive) scan and a ZAP **API** scan (active) driven by
   `/openapi.json`.
4. Uploads both reports as the `zap-reports` artifact.
5. Fails only on **High**-risk alerts. Medium and Low alerts appear in the report and
   are triaged, not gated.

Auth is disabled in this ephemeral stack so ZAP reaches every route. Never point the
workflow at a shared or production environment.

---

## Enabling the features (checklist)

1. Install the controllers listed in `deploy/k8s/platform-addons/README.md`.
2. AWS: set `karpenter_enabled` / `velero_enabled` on the EKS module, then apply the
   manifests from `deploy/k8s/platform-addons/karpenter/` and `velero/`.
3. Chart: add an environment overlay with `rollouts.enabled: true`, per-service
   `rollout.enabled` / `keda.enabled`, and `externalSecrets.enabled: true`. Use
   `deploy/helm/golden/ci/platform-addons-values.yaml` as a template.
4. Apply `security/policies/kyverno/`, starting in `Audit` if any existing images were
   pushed before signing was introduced.
