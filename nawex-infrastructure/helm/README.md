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

### 2. High-Speed Data Transport & State
*These charts manage the high-speed data transport required for background tasks and asynchronous AI processing.*

#### `redis/`
* **Purpose:** Deploys an isolated **Redis** instance as a high-performance message broker.
* **Problem Solved:** **Synchronous Bottlenecks.** Prevents primary application APIs from slowing down by offloading intensive AI/ML remediation tasks to background workers.
* **Value:** Provides a low-latency transport layer for [Celery](https://github.com/celery/celery) task queues, enabling distributed and asynchronous AI-driven infrastructure remediation.

---

### 3. Traffic Management & Security
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

### 4. Application & Developer Experience
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

### 5. Fintech Services
*These charts deploy the payment processing and fraud detection infrastructure.*

#### `fraud-detection/`
* **Purpose:** Deploys the **Fraud Detection** ML inference service as a highly available deployment with auto-scaling.
* **Problem Solved:** **Transaction Fraud.** Provides real-time ML-based fraud scoring for every transaction with sub-50ms latency.
* **Value:** Enables PCI-DSS compliant fraud prevention with automated model hot-swap and multi-AZ resilience. Includes strict network policies for CDE isolation.

#### `payment-gateway/`
* **Purpose:** Deploys the **Payment Gateway** processing service with automated failover capability.
* **Problem Solved:** **Payment Downtime.** Ensures payment processing remains available during infrastructure failures with automatic failover to secondary gateways.
* **Value:** Enforces PCI-DSS CDE segmentation with deny-all network policies, strict pod security contexts, and pod disruption budgets for zero-downtime deployments.

---

### 6. Healthcare Services
*These charts deploy the clinical data processing and patient safety infrastructure.*

#### `ehr-service/`
* **Purpose:** Deploys the **EHR Ingestion** service as a highly available deployment with auto-scaling and HIPAA-compliant PHI audit logging.
* **Problem Solved:** **Clinical Data Availability.** Provides reliable FHIR R4 clinical data ingestion with 99.999% availability for patient-safety-critical workflows.
* **Value:** Enables HIPAA-compliant EHR processing with automated breach detection, consent verification, and multi-AZ resilience. Includes PHI encryption at rest and strict network policies.

#### `clinical-gateway/`
* **Purpose:** Deploys the **Clinical Gateway** (Patient Data Gateway) with automated failover for FHIR/HL7 interoperability.
* **Problem Solved:** **Clinical Interoperability Downtime.** Ensures clinical data exchange remains available across EHR systems (Epic, Cerner, Meditech) during infrastructure failures.
* **Value:** Enforces HIPAA access controls with deny-all network policies, patient consent verification, and pod disruption budgets for zero-downtime clinical operations.

---

### Usage Guide

These charts are designed to be deployed via **ArgoCD** (GitOps). Do not run `helm install` manually in production.

**To deploy a new instance:**
1. Update the `values.yaml` in the respective environment folder (e.g., `gitops/envs/prod`).
2. Commit the change to Git.
3. ArgoCD will automatically sync the state.

---

*Copyright (c) 2026 Nawex Platform (NAWEX). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
