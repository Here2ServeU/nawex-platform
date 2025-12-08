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

Based on your request to standardize the format, here is the `docs/splunk-observability.md` file block rewritten to match the "Create New File" style of the others.

### Create New File: `docs/splunk-observability.md`

*Action: Create this file in the `docs/` folder.*

```markdown
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
```
