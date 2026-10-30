# AI Infrastructure Demo: 30 Minutes, EKS · AKS · GKE

A recorded walkthrough for AI infrastructure, GPU platform and MLOps roles. It covers five claims and proves each one from code or from a command run on screen:

| # | Claim | Proven by |
|---|---|---|
| 1 | GPU infrastructure on Kubernetes across EKS, AKS and GKE, with GPU pools that scale to zero | Terraform modules + `terraform plan` on all three clouds |
| 2 | NVIDIA GPU Operator, DCGM metrics, MIG and time-slicing | Operator config, sharing configs, `golden gpu partition`, DCGM alert rules |
| 3 | LLM and model serving with inference autoscaling, canary rollouts and observability | KServe InferenceService, vLLM on GPU, Argo Rollouts + Prometheus analysis |
| 4 | MLOps: KServe, MLflow, Kubeflow Pipelines, drift detection, promotion gates | Kubeflow pipeline, MLflow registry, live drift → retrain → **refused** promotion |
| 5 | SRE: SLOs, OpenTelemetry, GitOps across clouds, incident response | Burn-rate rules, OTel pipeline, one GitOps fleet (EKS/GKE/AKS), chaos drills |

The runner shows everything on screen in order and pauses between steps:

```bash
scripts/demo/ai-infra-demo.sh <segment>
```

## Repositories

Clone all of these into one folder (for example `~/golden`). The runner looks for them next to this repo.

| Repo | Role in the demo |
|---|---|
| [nawex-platform](https://github.com/Here2ServeU/nawex-platform) | **The spine.** EKS/AKS/GKE modules with GPU pools, GPU Operator, KServe, vLLM, Triton, Argo Rollouts, model lifecycle CLI, SLO rules, chaos |
| [nawex-ai-ml-infrastructure](https://github.com/Here2ServeU/nawex-ai-ml-infrastructure) | GitOps fleet: `dev-eks`, `staging-gke`, `prod-aks` with Argo CD or Flux; SLO policy |
| [nawex-observability-case-study](https://github.com/Here2ServeU/nawex-observability-case-study) | OpenTelemetry pipeline; live KServe + MLflow + drift demo on kind |
| [kubeflow-ml-pipeline](https://github.com/Here2ServeU/kubeflow-ml-pipeline) | Kubeflow pipeline with an accuracy gate before deploy |
| [mlflow-experiment-tracking](https://github.com/Here2ServeU/mlflow-experiment-tracking) | MLflow tracking and model registry |
| [openshift-k8s-ai-infra](https://github.com/Here2ServeU/openshift-k8s-ai-infra) | Optional depth: Karpenter GPU NodePool, KEDA, OpenShift GPU |

## Three ways to record it

| Mode | What runs | Cost | When to pick it |
|---|---|---|---|
| **A. Code + plans** (default) | Everything except live GPU nodes. Terraform *plans* on all three clouds; model lifecycle runs for real on your laptop. | $0 | Always works. Start here. |
| **B. A + local live stack** | Adds the kind cluster from `nawex-observability-case-study/demo`: KServe, MLflow, Grafana, drift and SLO-burn scenarios. | $0 (laptop with 6 CPU / 10 GB for Docker) | Strongest free option. |
| **C. B + one live GPU cluster** | `GPU_ENABLED=1 scripts/deploy.sh <cloud> dev apply` on **one** cloud, record segment 2 live with `LIVE=1`, then destroy. | One T4/A10G-class GPU node plus the control plane and load balancer for about an hour. Check current pricing; on-demand T4/A10G nodes are typically around $0.50 to $1.50 per hour. | When you want "here it is running on a GPU". |

**GPU quota.** New accounts start with zero GPU quota on all three clouds, and approval can take one to several days. Request it now if you want mode C. `preflight` prints exactly what to request.

## Before you record

```bash
cd ~/golden/nawex-platform
make bootstrap                                  # creates .venv and the golden CLI
scripts/demo/ai-infra-demo.sh preflight         # tools, logins, sibling repos, quota hints
GCP_PROJECT=<your-project> scripts/demo/ai-infra-demo.sh prep   # 3 terraform plans → demo_output/ai-infra/
```

- `prep` needs credentials for each cloud and a `terraform.tfvars` in `deploy/terraform/live/<cloud>/dev/`. Copy it from `terraform.tfvars.example`.
- `prep` creates nothing. It only runs `plan`.
- If a cloud plan fails, set `CLOUDS="aws gcp"` (and so on) and show the module code for the other cloud.

Screen setup:

- Terminal at 16 pt or larger, dark theme. Install `bat` for nicer file views.
- Run `PAUSE=1` (the default) so you can talk at each step.
- Optional tabs: Grafana (mode B), the GitHub repo pages, and the cloud console.

## Run of show

Times are targets. Rehearse once against a timer; the most common overrun is segment 1.

### 0:00 to 2:00 · Opening

On screen: GitHub profile, then the `nawex-platform` README.

> "I'm Emmanuel Naweji. I've run production infrastructure for more than ten years, and my focus now is the platform under AI workloads: GPUs on Kubernetes, model serving, MLOps, and the SRE practice that keeps them reliable.
>
> In the next 30 minutes I'll show five things, each one backed by code or a command you'll see run: GPU infrastructure across EKS, AKS and GKE; the NVIDIA GPU stack with DCGM, MIG and time-slicing; LLM and model serving with autoscaling and canaries; an MLOps loop with drift detection and a promotion gate that refuses a weaker model; and the SRE layer with SLOs, OpenTelemetry and GitOps across all three clouds.
>
> These are reference platforms I designed and built. Where something runs live, you'll see it. Where it's a plan or a design target, I'll say so."

### 2:00 to 8:00 · Segment 1: one GPU landing zone, three clouds

```bash
scripts/demo/ai-infra-demo.sh clouds
```

Talk track:

- **The contract.** "Every cloud gets the same contract: a general node pool, plus a GPU pool that scales from zero, labelled `nvidia.com/gpu.present` and tainted so only GPU workloads land there. GPUs are the most expensive thing in the cluster, so an idle GPU pool should cost nothing."
- **EKS.** "On EKS that's a managed node group on the AL2023 NVIDIA AMI with `min_size = 0`, IRSA for pod identity, and Karpenter discovery tags."
- **AKS.** "On AKS it's a dedicated autoscaling node pool with `min_count = 0` and the same taint, next to a Spot pool for batch, with Workload Identity."
- **GKE.** "On GKE it's a node pool with a guest accelerator, Google-managed driver install, the same taint and labels, and Workload Identity on the nodes."
- **The switch.** "One switch turns it on per environment: `GPU_ENABLED=1` adds the pool in Terraform and schedules the GPU workloads in Helm."
- **The plans.** On the saved plans: "Here's `terraform plan` on all three clouds with the GPU pool enabled. Same module interface, three providers."

If asked why not one module for all three clouds: "The clouds differ where it matters: driver install, identity, autoscaler. A shared interface with three honest implementations is easier to operate than one leaky abstraction."

### 8:00 to 13:00 · Segment 2: GPU Operator, DCGM, MIG, time-slicing

```bash
scripts/demo/ai-infra-demo.sh gpu          # add LIVE=1 in mode C
```

Talk track:

- **The operator.** "The NVIDIA GPU Operator manages the whole node stack: driver, container toolkit, device plugin, GPU feature discovery, the MIG manager, and the DCGM exporter. The chart version is pinned because an upgrade rolls new drivers onto every GPU node. On managed images that already ship the driver, I turn the driver install off."
- **DCGM.** "DCGM exporter is on, with a ServiceMonitor, so utilization, memory, temperature and Xid errors go into Prometheus. These alert rules use DCGM metrics directly: thermal, under-utilization, Xid errors."
- **Sharing modes.**
  - "Time-slicing advertises one GPU as four, which is good for notebooks and light inference, with no memory isolation."
  - "MIG gives hard isolation: a 3g.40gb slice for an LLM and 1g.10gb slices for small models."
  - "I pick per workload, not per cluster."
- **The planner.** "This planner packs a sample workload mix across GPUs and picks whole-GPU, MIG or time-slicing for each one. With a $6 per GPU-hour *assumption*, it needs four GPUs instead of five. That's modelled savings, not a measured bill."
- **Mode C only.**
  - "Here's the live node: GPU product label, MIG state and replica count."
  - "Allocatable shows `nvidia.com/gpu` multiplied by time-slicing."
  - "And raw DCGM metrics straight from the exporter."

### 13:00 to 19:00 · Segment 3: LLM and model serving

```bash
scripts/demo/ai-infra-demo.sh serving
```

Talk track:

- **KServe.** "Classic models are served by KServe. Autoscaling is on in-flight requests, not CPU: a target of 20 concurrent requests per pod, two to ten replicas. CPU is a poor signal for inference."
- **Scale to zero, deliberately.** "Note the minimum of two: a fraud decision path never scales to zero, because a cold start is an outage there. Scale-to-zero belongs on the GPU *node pool* and on batch or internal models, not on a latency-critical endpoint."
- **Model canary.** "A new model version goes out as a KServe canary: 10% of traffic to the new revision, the rest stays on the old one. To promote, set it to 100. To roll back, set it to 0. It's one field in Git."
- **vLLM.** "LLMs run on vLLM with an OpenAI-compatible API. It's pinned to the GPU pool with a node selector and a toleration, requests one GPU, and has a readiness probe so it gets no traffic until the model is loaded. Model weights are cached so a rollout doesn't re-download them."
- **Argo Rollouts.** "The platform services around the models ship as Argo Rollouts: 10%, 25%, 50%, with pauses. An AnalysisTemplate queries Prometheus for success rate of at least 99% and p95 under 500 ms, on canary pods only. Two bad measurements and the rollout aborts itself."
- **Observability.** "Every service exposes the same metrics, so the same dashboards and burn-rate alerts cover serving end to end."

If asked about GPU autoscaling for LLMs: "Scale on queue depth or KV-cache use, not CPU or GPU utilization. KEDA on a Prometheus query works well, and the GPU pool's cluster autoscaler adds nodes when pods are pending. The KEDA and Karpenter setup is in `openshift-k8s-ai-infra/platform/`."

### 19:00 to 25:00 · Segment 4: MLOps

```bash
scripts/demo/ai-infra-demo.sh mlops
```

Talk track:

- **Pipeline.** "The training pipeline is Kubeflow: load, preprocess, train, evaluate, then deploy only if accuracy clears the threshold. A model that fails the gate never reaches serving."
- **Registry.** "Runs are tracked in MLflow, and the best run is registered in the model registry."
- **Drift.** Run it live. "This compares today's traffic with the training baseline using PSI and a KS test.
  - Note the result: KS says the distribution has shifted, but PSI is still in the stable band.
  - That's why I use both. KS catches a shift early on large samples; PSI tells you whether it's big enough to act on."
- **Retrain.** "Drift triggers a retrain. The first model becomes champion. The retrain on new data passes the minimum quality gate, so it's registered as a challenger."
- **The gate.** This is the key moment. "Now I try to promote the challenger. Promotion needs a named approver, and the challenger can't be worse than the champion on the primary metric, which is recall for fraud. Its recall is 0.93 against 0.95, so it's **refused**. No human can accidentally ship a weaker model."
- **Mode B.** In the kind cluster, run `make scenario-drift` and show the Grafana model-drift dashboard and the KServe InferenceService.

Note: all metrics here are on synthetic data with fixed seeds, and they reproduce exactly. Say so if asked.

### 25:00 to 29:00 · Segment 5: SRE across three clouds

```bash
scripts/demo/ai-infra-demo.sh sre
```

Talk track:

- **SLOs.** "SLOs are code, for availability and latency. Alerts are multi-window burn rates: a 14.4× burn over an hour pages someone, and a 6× burn over six hours opens a ticket. That's the Google SRE Workbook model, and it ends 3 a.m. pages for blips."
- **GitOps fleet.** "One GitOps fleet: dev on EKS, staging on GKE, prod on AKS. Each cluster reconciles from its own folder, with Argo CD or Flux, the same Helm charts, and promotion by pull request."
- **OpenTelemetry.** "One OpenTelemetry pipeline, with agent and gateway collectors, feeds Prometheus, Grafana and Splunk. Teams instrument once."
- **Chaos.** "Chaos drills prove the alerts and the recovery paths. Each alert has a runbook."
- **Your record.** "In my roles I've delivered 99.99% availability across multi-cloud Kubernetes on AWS, Azure and GCP. These repos are how I'd build that platform again from scratch."

### 29:00 to 30:00 · Close

> "To recap: GPU pools that scale to zero on EKS, AKS and GKE; the NVIDIA operator with DCGM, MIG and time-slicing; serving with KServe and vLLM, autoscaled on requests and shipped by canary; an MLOps loop that refuses a weaker model; and SRE with burn-rate SLOs and one GitOps fleet across three clouds. All the code is on my GitHub. Thanks for watching."

## Honest answers to likely questions

- **"Is this running in production?"** "These are reference platforms I built and run locally and in CI. The production experience comes from my roles; this is my own build of the same patterns." If you ran mode C: "I deployed the GPU pool on <cloud> for this recording."
- **"Have you used Triton / NIM / NCCL / Slurm / InfiniBand?"** There is a Triton manifest in `deploy/k8s/ml-serving/triton.yaml`. Only claim the tools you have actually run. For anything else: "Not in production yet. Here's how I'd approach it."
- **"Where's the number from?"** Every number on screen comes from a command shown on screen, or is labelled as an assumption (GPU price) or a target (SLOs). See [CLAIMS.md](../CLAIMS.md).

## After recording

- Destroy anything you created in mode C:

  ```bash
  scripts/deploy.sh <cloud> dev destroy
  ```

  Then check the console for leftover load balancers and disks.

- Cut chapters at the segment boundaries. Use YouTube chapter markers with the same times as above.
- Put the video link in the README of `nawex-platform` and on your resume's project line.
