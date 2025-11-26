# /gitops — ArgoCD & FluxCD GitOps Layer

This directory defines the GitOps control plane for the **Express AI-Driven Multi-Cloud Resilience Platform** using **ArgoCD** and **FluxCD**.

It provides:

- Application manifests (ArgoCD Applications, Flux HelmReleases/Kustomizations)
- References to the `/helm` charts in this repo
- Cluster add-ons (ArgoCD / Flux bootstrap)
- Drift detection (auto-sync & self-heal)
- SOC 2–friendly, blame-free audit trail via Git history and GitOps events

## Layout

- `argocd/`
  - `namespace.yaml` – installs `argocd` namespace
  - `project-platform.yaml` – ArgoCD Project for platform apps
  - `app-express-app.yaml` – ArgoCD Application for the Express app (v7)
  - `app-monitoring-stack.yaml` – ArgoCD Application for Prometheus + Grafana
  - `app-backstage.yaml` – ArgoCD Application for Backstage IDP
  - `app-kafka-zookeeper.yaml` – ArgoCD Application for Kafka + Zookeeper

- `flux/`
  - `namespace.yaml` – `flux-system` namespace
  - `gitrepository-platform.yaml` – Flux source pointing to this Git repo
  - `kustomization-platform.yaml` – Top-level Kustomization for all apps
  - `apps/express-app-helmrelease.yaml` – Flux HelmRelease for Express app
  - `apps/monitoring-helmrelease.yaml` – Flux HelmRelease for monitoring

- `policies/`
  - `soc2-gitops-controls.md` – Explains how GitOps supports SOC 2 controls
  - `drift-detection.md` – How ArgoCD/Flux detect & self-heal drift

## Usage (ArgoCD)

1. Install ArgoCD into the cluster (e.g., via upstream manifests):

```bash
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f gitops/argocd/namespace.yaml
kubectl apply -f gitops/argocd/project-platform.yaml
kubectl apply -f gitops/argocd/app-express-app.yaml
kubectl apply -f gitops/argocd/app-monitoring-stack.yaml
kubectl apply -f gitops/argocd/app-backstage.yaml
kubectl apply -f gitops/argocd/app-kafka-zookeeper.yaml
```

2. ArgoCD will:
   - Continuously watch this Git repository
   - Detect drift between live & desired state
   - Auto-sync & self-heal when `syncPolicy.automated` is enabled

## Usage (FluxCD)

1. Install Flux CLI & controllers:

```bash
kubectl create namespace flux-system
flux install --namespace flux-system
```

2. Apply the Git source + Kustomization and HelmReleases:

```bash
kubectl apply -f gitops/flux/namespace.yaml
kubectl apply -f gitops/flux/gitrepository-platform.yaml
kubectl apply -f gitops/flux/kustomization-platform.yaml
kubectl apply -f gitops/flux/apps/express-app-helmrelease.yaml
kubectl apply -f gitops/flux/apps/monitoring-helmrelease.yaml
```

Flux will then:
- Reconcile on a schedule (e.g., every minute)
- Detect drift & reconcile back from Git
- Provide a clear event history for audits
