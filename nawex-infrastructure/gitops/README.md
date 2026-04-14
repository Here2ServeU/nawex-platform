# GitOps Control Plane

**Automated Configuration Management for the Express AI-Driven Platform**

This directory defines the GitOps control plane, utilizing **ArgoCD** and **Flux** to manage the lifecycle of the Web App Workload, Observability Stack, and Platform Infrastructure. It enforces a "Code is Law" philosophy, ensuring that the desired state defined in Git is always reflected in the cluster.

---

## Directory Layout

### 1. ArgoCD (Application Layer)
Located in `argocd/`. Manages high-level applications and ensuring continuous synchronization.

* `namespace.yaml`: Bootstraps the `argocd` namespace.
* `project-platform.yaml`: Defines the ArgoCD Project with restricted source/destination policies.
* `app-express-app.yaml`: Deploys the **Web App Workload** (Node.js/Express).
* `app-splunk-forwarder.yaml`: Deploys the Splunk Universal Forwarder DaemonSet.
* `app-monitoring-stack.yaml`: Deploys Prometheus and Grafana for metrics.
* `app-kafka-zookeeper.yaml`: Deploys the event streaming backbone.

### 2. Flux (Infrastructure Layer)
Located in `flux/`. Manages low-level cluster resources and automated reconciliation.

* `namespace.yaml`: Bootstraps the `flux-system` namespace.
* `gitrepository-platform.yaml`: Defines the source connection to this repository.
* `kustomization-platform.yaml`: The top-level entry point for infrastructure reconciliation.
* `apps/express-app-helmrelease.yaml`: HelmRelease definition for the Web App.
* `apps/resources/splunk-forwarder-helmrelease.yaml`: HelmRelease for Splunk logging.

### 3. Policies (Compliance & Security)
Located in `policies/`. Documentation on how this architecture satisfies regulatory controls.

* `drift-detection.md`: Explains the auto-sync and self-heal mechanisms.
* `soc2-gitops-controls.md`: Details how GitOps meets SOC 2 Type II requirements (Change Management, Audit Trails).

---

## Usage Guide: ArgoCD

To bootstrap the Application Layer using ArgoCD:

1. **Install ArgoCD** (if not already present):
    ```bash
    kubectl apply -n argocd -f [https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml](https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml)
    ```

2. **Apply Platform Manifests**:
    ```bash
    kubectl apply -f gitops/argocd/namespace.yaml
    kubectl apply -f gitops/argocd/project-platform.yaml
    ```

3. **Deploy Applications**:
    ```bash
    kubectl apply -f gitops/argocd/app-express-app.yaml
    kubectl apply -f gitops/argocd/app-splunk-forwarder.yaml
    ```

**Result:** ArgoCD will begin synchronizing the Web App and Splunk Forwarder immediately.

---

## Usage Guide: Flux

To bootstrap the Infrastructure Layer using Flux:

1. **Install Flux CLI & Controllers**:
    ```bash
    flux install --namespace flux-system
    ```

2. **Apply Source & Kustomization**:
    ```bash
    kubectl apply -f gitops/flux/namespace.yaml
    kubectl apply -f gitops/flux/gitrepository-platform.yaml
    kubectl apply -f gitops/flux/kustomization-platform.yaml
    ```

**Result:** Flux will enter a continuous reconciliation loop (1-minute interval), ensuring that any drift in the `helm/` charts is instantly corrected.

---

*Copyright (c) 2026 Nawex Platform (NAWEX). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
