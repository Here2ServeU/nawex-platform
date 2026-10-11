# ArgoCD Control Plane & Application Manifests

This directory contains the **ArgoCD Application** definitions. While the `deploy/helm/` directory contains the *blueprints* (templates), this directory contains the *instructions* that tell ArgoCD where to deploy those blueprints and with what parameters.

These manifests act as the binding layer between the Git repository and the Kubernetes cluster, enforcing the **"Code is Law"** philosophy of GitOps.

## Directory Structure

* **`app-golden.yaml`**: ArgoCD definition for the Golden platform services (`deploy/helm/golden`).
* **`app-openshift-virtualization.yaml`**: OpenShift Virtualization + MTV operators for VMware migration.
* **`app-splunk-forwarder.yaml`**: ArgoCD definition for the Splunk Universal Forwarder (Log Shipping).
* **`app-monitoring-stack.yaml`**: ArgoCD definition for the Prometheus & Grafana stack (Metrics & Dashboards).
* **`app-datadog.yaml`**: ArgoCD definition for the Datadog Agent (Unified Observability).
* **`app-dynatrace.yaml`**: ArgoCD definition for the Dynatrace Operator (Full-Stack Intelligence).

*(All manifests follow the standard "App of Apps" pattern, pointing to their respective charts in `deploy/helm/` or upstream vendor Helm repositories.)*

## Core Capabilities & SRE Value

### 1. Automated Drift Detection & Self-Healing
* **Problem:** "Snowflake Clusters." Administrators making manual changes via `kubectl edit` that are lost during the next update.
* **Solution:** These manifests configure ArgoCD to monitor the cluster state every 3 minutes. If a manual change is detected, ArgoCD flags it as "Out of Sync."
* **Impact:** **Immutability.** If enabled, the `selfHeal` policy instantly reverts manual changes, ensuring the cluster always matches the Git repo.

### 2. The "App of Apps" Pattern
* **Problem:** Manually applying 50 different `.yaml` files to bootstrap a new cluster.
* **Solution:** We can create a parent "Root App" that points to this directory. ArgoCD will then recursively discover and deploy every application defined here.
* **Impact:** **One-Click Disaster Recovery.** We can spin up a brand new production cluster in a new region by applying a single manifest.

### 3. Progressive Delivery Control
* **Problem:** Deploying a broken config to all environments simultaneously.
* **Solution:** These manifests allow us to override `values.yaml` for specific environments (e.g., setting `replicaCount: 1` for Staging vs `replicaCount: 50` for Prod) without changing the underlying Helm chart.
* **Impact:** **Safe Rollouts.** We can test changes in Staging using the exact same artifacts that will go to Production.

## Usage Guide

**To Deploy a New Service:**
1. Create a new file in this directory (e.g., `app-my-service.yaml`).
2. Paste the standard ArgoCD Application boilerplate.
3. Point the `source.path` to your Helm chart (e.g., `deploy/helm/my-service`).
4. Commit to Git. ArgoCD will automatically pick it up and deploy it.

**Example Manifest (Splunk):**
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: splunk-forwarder
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/Here2ServeU/nawex-platform
    targetRevision: HEAD
    path: deploy/helm/splunk-forwarder
  destination:
    server: '[https://kubernetes.default.svc](https://kubernetes.default.svc)'
    namespace: monitoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
````

### Talking Point

> I organize my `gitops/argocd` folder to separate the *definition* of the app from the *deployment* of the app. By keeping these manifests distinct from the Helm charts, I can manage multi-cluster deployments easily. For example, I can have an `app-prod.yaml` and `app-stage.yaml` that both point to the same chart but apply different sync policies or environment variables.

---

*Copyright (c) 2026 Nawex Platform (NAWEX). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
