# Splunk Observability Integration

**Centralized Logging & SIEM for the Express AI-Driven Multi-Cloud Resilience Platform**

This document details the architecture and integration flow of **Splunk Enterprise** within the platform. It serves as the primary data lake for long-term retention, security forensics (SIEM), and deep-dive operational analytics, complementing the real-time telemetry collected by the **Observer Agent**.

---

## Architecture Components

The Observability stack is built on a distributed forwarding model ensuring 100% log capture across multi-cloud environments.

### 1. Splunk Enterprise Core
* **Deployment:** Automated provisioning via Terraform on **AWS EC2**, **Azure VM**, **GCP Compute**, or **OCI Compute**.
* **Ingestion:** HTTP Event Collector (HEC) exposed on port `8088`.
* **Role:** Indexing, Search Head, and Dashboarding.

### 2. Universal Data Collection
* **Kubernetes:** A `splunk-forwarder` DaemonSet (deployed via Helm) runs on every node, capturing:
    * Container STDOUT/STDERR (including **Web App** workload logs).
    * Kubelet system logs.
    * Audit logs.
* **Virtual Machines:** Fluent Bit forwarders configured to ship `/var/log/*` directly to the HEC endpoint.

### 3. GitOps Management
* **ArgoCD:** Manages the lifecycle of the Splunk Forwarder configurations (`gitops/argocd/app-splunk-forwarder.yaml`).
* **Flux:** Ensures immutable configuration state across clusters (`gitops/flux/apps/resources/splunk-forwarder-helmrelease.yaml`).

---

## Data Flow

1. **Generation:** The **Web App Workload** generates structured JSON logs (Latency, Errors, CPU).
2. **Collection:** The `splunk-forwarder` DaemonSet intercepts these logs at the node level.
3. **Ingestion:** Logs are encrypted and pushed to the central Splunk HEC endpoint.
4. **Analysis:**
    * **SRE Teams:** Use Splunk dashboards for historical trend analysis and incident post-mortems.
    * **AIOps Engine:** (Future Integration) The `ObserverAgent` can query Splunk APIs to retrain LSTM/TCN models with historical datasets.

---

## Key Dashboards

| Dashboard Name | Purpose | Key Metrics |
| :--- | :--- | :--- |
| **Multi-Cloud Overview** | Executive view of health across AWS/Azure/GCP. | Uptime, Global Request Rate, Cost Velocity. |
| **Web App Performance** | Deep dive into the Node.js workload. | P95 Latency, Error Rates by Endpoint, Heap Usage. |
| **Security & Compliance** | SOC 2 / HIPAA audit trail. | Failed Logins, IAM Changes, Unusual Access Patterns. |

---

## Setup Guide

### 1. Provision Infrastructure
```bash
cd terraform/live/aws/splunk
terraform apply -auto-approve
# Output: splunk_hec_endpoint, splunk_admin_token

---

*Copyright (c) 2026 Nawex Platform (NAWEX). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
