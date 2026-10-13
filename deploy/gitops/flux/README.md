# FluxCD Infrastructure Management

This directory contains the **FluxCD** configuration for the platform. While ArgoCD is used for application delivery (visualized in the "App of Apps" pattern), FluxCD is utilized here to demonstrate an alternative "headless" GitOps workflow, often preferred for bootstrapping the underlying cluster infrastructure itself.

## Directory Structure

* **`apps/resources/`**: Contains the `HelmRelease` definitions. These Custom Resources (CRs) instruct the Flux Helm Controller to install charts from the local `deploy/helm/` directory.
    * `splunk-forwarder-helmrelease.yaml`: Log shipping agent.
    * `monitoring-stack-helmrelease.yaml`: Prometheus & Grafana.
    * `datadog-helmrelease.yaml`: Datadog agent.

## Core Capabilities & SRE Value

### 1. Automated Drift Correction
* **Concept:** The Flux Controller polls this Git repository every 5 minutes.
* **Value:** If an administrator manually changes a Kubernetes deployment (e.g., changing a replica count via `kubectl`), Flux detects the drift and immediately reverts it to the state defined in Git. This enforces **Immutable Infrastructure**.

### 2. Source-Controller Architecture
* **Concept:** Unlike ArgoCD's "Push" model (where the server connects to the repo), Flux pulls artifacts into the cluster.
* **Value:** **Security Hardening.** The cluster does not need to expose any inbound ports or webhooks to the outside world. It reaches *out* to GitHub to fetch updates.

### 3. Helm Integration
* **Concept:** The `HelmRelease` object wraps the standard Helm chart.
* **Value:** We get the best of both worlds: the templating power of Helm (for defining the app) and the automation of Flux (for deploying the app).

## Usage Guide

**To Add a New Service:**
1. Create a standard Helm chart in the `deploy/helm/` directory.
2. Add a new `.yaml` file in `apps/resources/` defining the `HelmRelease`.
3. Update `kustomization.yaml` to include the new file.
4. Commit to Git. Flux will pick up the change automatically.

### Interview Talking Point:
> You might notice I have both argocd and flux folders. I built it this way to demonstrate proficiency with both industry standards. In a real-world scenario, I often use Flux for the low-level cluster bootstrapping (CNI, CSI, Service Mesh) because it's lightweight and headless, and then I layer ArgoCD on top for the developer-facing applications so they get the nice UI.

---

*Copyright (c) 2026 Nawex Platform (NAWEX). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
