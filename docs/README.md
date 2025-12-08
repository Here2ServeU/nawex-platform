# Engineering Knowledge Base & Architecture

This directory serves as the **Single Source of Truth** for the platform's architectural design, decision records, and operational guides.

Following the **"Docs-as-Code"** methodology, all documentation is version-controlled alongside the application code. This ensures that the documentation evolves in lockstep with the infrastructure, preventing the common "stale wiki" problem.

## Directory Structure

### Architectural Deep Dives
These documents detail the implementation strategies for our observability backends.

* **File:** [`splunk-observability.md`](./splunk-observability.md)
    * **Focus:** **Log Aggregation Strategy.**
    * **Key Decisions:** Universal Forwarder vs. HEC, Index Segmentation (`main` vs. `audit`), and Data Retention policies.

* **File:** [`prometheus-grafana.md`](./prometheus-grafana.md)
    * **Focus:** **Open Source Metrics & Alerting.**
    * **Key Decisions:** "Pull" model architecture, `ServiceMonitor` CRD usage, and "Dashboards-as-Code" lifecycle management.

* **File:** [`datadog-observability.md`](./datadog-observability.md)
    * **Focus:** **Unified SaaS Monitoring.**
    * **Key Decisions:** Agent-based collection (DaemonSet), APM trace sampling rates, and Cost Management (custom metrics filtering).

* **File:** [`dynatrace-intelligence.md`](./dynatrace-intelligence.md)
    * **Focus:** **AI-Driven Root Cause Analysis.**
    * **Key Decisions:** OneAgent Operator deployment, Davis AI integration for automated problem detection, and "PurePath" distributed tracing.

### Diagrammatic Source Code (`diagrams/`)
* **Focus:** **Visual Architecture.**
* **Content:** Contains the *source code* for system diagrams, primarily using **Mermaid.js** (`.mmd`).
* **Why Code?** Unlike static PNGs, these text-based diagrams can be edited, versioned, and rendered dynamically.

## Documentation Standards
1. **Context over Config:** We explain the *why*, not just the *what*.
2. **Living Artifacts:** Every PR that changes the stack must update these docs.
3. **Incident Readiness:** Written for the "3 AM On-Call Engineer."
```

-----

### 2\. `docs/splunk-observability.md`

# Splunk Log Aggregation Strategy

## Overview
This document details our **Hybrid Log Aggregation** strategy using Splunk. We treat logs as our "Source of Truth" for forensic analysis and security auditing, prioritizing 100% data retention and tamper-proof storage.

## Architecture Decisions

### 1. Universal Forwarder (DaemonSet)
* **Decision:** We deploy the Splunk Universal Forwarder (UF) as a DaemonSet on every Kubernetes node.
* **Why:** This provides the most resource-efficient way to capture standard container logs (`stdout`/`stderr`). A single agent per node handles all pod traffic, preventing the "sidecar bloat" that occurs when running logging agents inside every pod.
* **Config:** The UF monitors `/var/log/containers/*.log` and decorates events with Kubernetes metadata (Namespace, Pod Name, Container ID) before shipping.

### 2. HTTP Event Collector (HEC)
* **Decision:** We enable the HTTP Event Collector (HEC) for serverless and event-driven workloads.
* **Why:** Traditional file tailing doesn't work for ephemeral functions (like AWS Lambda or Google Cloud Functions) or third-party webhooks. HEC allows these services to POST JSON payloads directly to Splunk.
* **Security:** Tokens are managed via Kubernetes Secrets (see `helm/splunk-hec/templates/secret.yaml`) and rotated quarterly.

### 3. Index Segmentation (Security & Compliance)
* **Strategy:** We segregate data into distinct indexes based on sensitivity and retention requirements.
    * **`main` Index:** Application logs. Retention: 30 days. Accessible by all developers.
    * **`audit` Index:** Authentication logs, sudo commands, and K8s API audit trails. Retention: 1 year (Cold Storage). Accessible only by Security/SRE.
    * **`pci` Index:** Logs from the payment gateway namespace. Strict access controls applied.

### 4. Data Retention & Lifecycle
* **Policy:** "Hot" storage for 7 days (NVMe SSD) for fast searching, moving to "Cold" storage (S3-backed) for long-term compliance.
* **Impact:** Balances search performance with storage costs.

-----

### 3\. `docs/prometheus-grafana.md`

*Create this file.*

```markdown
# Prometheus & Grafana Architecture

## Overview
This document outlines the **Metrics-First** observability strategy using the cloud-native Prometheus stack. While Splunk handles logs, Prometheus provides the high-speed, real-time "heartbeat" of the cluster.

## Architecture Decisions

### 1. The "Pull" Model
Unlike the "Push" model used by Datadog/Splunk agents, Prometheus **scrapes** metrics from targets.
* **Decision:** We use the `ServiceMonitor` Custom Resource Definition (CRD).
* **Why:** It allows development teams to define *how* their app should be scraped (port, path, interval) alongside their application code, adhering to self-service principles.

### 2. High Availability (Thanos Integration)
* **Challenge:** Prometheus is stateful and difficult to scale horizontally.
* **Solution:** We deploy **Thanos Sidecars** to upload old metric blocks to Object Storage (S3/GCS).
* **Impact:** Enables unlimited retention and a global query view across multiple clusters without bloating local disk.

### 3. Dashboards as Code
* **Policy:** No manual edits in the Grafana UI.
* **Workflow:** Dashboards are defined as JSON in the `helm/monitoring-stack/dashboards` folder.
* **Automation:** A sidecar container watches that folder and calls the Grafana API to reload changes instantly.
```

-----

### 4\. `docs/datadog-observability.md`

*Create this file.*

```markdown
# Datadog Unified Observability

## Overview
This document details the integration of **Datadog** as our primary SaaS observability platform for Application Performance Monitoring (APM) and Infrastructure correlation.

## Architecture Decisions

### 1. The Unified Agent (DaemonSet)
* **Decision:** We deploy the Datadog Agent as a DaemonSet on every node.
* **Why:** It automatically collects host-level metrics (CPU/Mem), container logs, and network traces without sidecars.
* **Config:** Managed via the `helm/datadog` chart using `values.yaml` overrides for different environments.

### 2. APM & Trace Sampling
* **Challenge:** Ingesting 100% of traces is cost-prohibitive.
* **Strategy:** We utilize **Tail-Based Sampling** logic.
    * **Keep:** All traces with `error=true` or `latency > 2s`.
    * **Drop:** 99% of successful health checks (`200 OK`).

### 3. Tagging Strategy (Unified Service Tagging)
* **Policy:** Every resource must possess three standard tags: `env`, `service`, and `version`.
* **Enforcement:** Validated by the OPA Gatekeeper policy in the `gitops/policies` directory.
* **Value:** Enables "Pivot" navigation in Datadog (jumping from Logs -> Metrics -> Traces for a specific version).
```

-----

### 5\. `docs/dynatrace-intelligence.md`

*Create this file.*

```markdown
# Dynatrace & Davis AI Integration

## Overview
This document covers the **Dynatrace** implementation, specifically focusing on its use for **Automated Root Cause Analysis (RCA)** via the Davis AI engine.

## Architecture Decisions

### 1. Operator-Based Injection
* **Decision:** We use the Dynatrace Operator (`dynatrace-operator`) rather than manual OneAgent installation.
* **Why:** It utilizes a MutatingWebhook to automatically inject the OneAgent loader into application pods at runtime.
* **Impact:** Zero-touch instrumentation. Developers do not need to add libraries to their Dockerfiles.

### 2. PurePath Distributed Tracing
* **Concept:** Dynatrace captures 100% of transactions (PurePaths) without sampling at the agent level.
* **Usage:** Used primarily for deep-dive debugging of complex microservice interactions that span hybrid clouds (e.g., On-Prem Database -> GKE Microservice).

### 3. Problem Detection Profiles
* **Config:** Custom alerting profiles are defined in `helm/dynatrace/profiles`.
* **Tuning:** We have tuned Davis AI to ignore "frequent but harmless" warnings (like transient high CPU during startup) to reduce alert fatigue.
```
