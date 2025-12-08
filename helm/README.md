# Helm Chart Repository & Service Catalog

This directory acts as the **Internal Service Catalog** for the platform. It contains the custom Helm charts used to deploy the core infrastructure and applications to Kubernetes (EKS, AKS, GKE, or OKE).

These charts are designed to be **immutable blueprints**, ensuring that every deployment—whether in Staging or Production—adheres to the same reliability, security, and observability standards.

---

### 1. The Observability Data Pipeline
*These charts form the backbone of the AIOps platform, handling the ingestion and transport of high-volume telemetry data.*

#### `otel-collector/`
* **Purpose:** Deploys the **OpenTelemetry Collector** as a DaemonSet/Sidecar.
* **Problem Solved:** **Vendor Lock-in.** Decouples the generation of traces/metrics from their destination.
* **Value:** Allows us to route the same telemetry stream to multiple backends (e.g., Splunk *and* Prometheus) without modifying application code.

#### `kafka-zookeeper/`
* **Purpose:** Deploys a high-availability **Kafka** cluster with Zookeeper coordination.
* **Problem Solved:** **Data Loss during Spikes.** Acts as a durable buffer for log and metric data before it is processed by the AIOps engine.
* **Value:** Ensures zero telemetry data loss even if the backend analysis tool is temporarily down or overwhelmed.

#### `splunk-forwarder/` & `splunk-hec/`
* **Purpose:** Deploys the Universal Forwarder and configures the HTTP Event Collector (HEC) tokens.
* **Problem Solved:** **Log Fragmentation.** Aggregates logs from all nodes and pods into a central secure pipeline.
* **Value:** Provides the raw data required for the `sre/aiops` pattern matching scripts to detect anomalies.

#### `monitoring-stack/`
* **Purpose:** Deploys the standard metrics suite (Prometheus, Grafana, Alertmanager).
* **Problem Solved:** **Blind Spots.** Provides out-of-the-box dashboards for Node, Pod, and Cluster health.
* **Value:** Gives immediate "Single Pane of Glass" visibility into infrastructure health.

---

### 2. Traffic Management & Security
*These charts enforce "Zero Trust" networking and manage ingress traffic.*

#### `service-mesh/`
* **Purpose:** Deploys the Service Mesh control plane (e.g., Istio/Linkerd).
* **Problem Solved:** **Insecure Internal Traffic.** Automatically injects mTLS (mutual TLS) sidecars to encrypt all pod-to-pod communication.
* **Value:** Enforces security compliance (encryption in transit) and enables advanced traffic strategies like **Canary Deployments** and **Circuit Breaking**.

#### `kong-gateway/`
* **Purpose:** Deploys the Kong API Gateway as the Ingress Controller.
* **Problem Solved:** **API Governance.** Centralizes authentication, rate-limiting, and routing rules at the edge.
* **Value:** Protects backend microservices from DDoS attacks and abusive usage patterns while simplifying API management.

---

### 3. Application & Developer Experience
*These charts standardize how developers interact with the platform.*

#### `express-app/`
* **Purpose:** A "Golden Path" chart for deploying stateless Node.js microservices.
* **Problem Solved:** **Configuration Drift.** Developers don't write their own Kubernetes manifests; they simply provide a Docker image and environment variables.
* **Value:** Enforces SRE best practices (Health Checks, Resource Limits, PDBs) by default for every application deployed.

#### `backstage/`
* **Purpose:** Deploys the Spotify Backstage developer portal.
* **Problem Solved:** **Service Discovery.** Provides a centralized catalog where developers can see the health, ownership, and documentation of all running microservices.
* **Value:** Reduces onboarding time and operational toil by giving developers a self-service UI to manage their services.

---

### Usage Guide

These charts are designed to be deployed via **ArgoCD** (GitOps). Do not run `helm install` manually in production.

**To deploy a new instance:**
1. Update the `values.yaml` in the respective environment folder (e.g., `gitops/envs/prod`).
2. Commit the change to Git.
3. ArgoCD will automatically sync the state.
