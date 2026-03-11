# Datadog APM & Observability Architecture

This document outlines the configuration and deployment strategy for Datadog APM within the Express AIOps Platform. The setup utilizes the Datadog Cluster Agent to provide seamless autodiscovery of pods and services running in Kubernetes.

## 1. Architecture Overview

The observability stack relies on the **Datadog Agent** running as a DaemonSet on every node. It collects:
- **Traces (APM):** End-to-end request tracking from Ingress → Express App → Databases/Kafka.
- **Logs:** Container stdout/stderr logs, correlated with Trace IDs.
- **Metrics:** Infrastructure stats (CPU, Memory) and Custom Metrics (DogStatsD).

## 2. Deployment Strategy

We deploy the agent using the official Helm chart.

### Key Configuration Flags
* **`datadog.apm.enabled=true`**: Activates the Trace Agent to accept spans.
* **`datadog.logs.enabled=true`**: Enables log tailing from `/var/log/containers`.
* **`datadog.processAgent.enabled=true`**: Visualizes live containers and process trees.

## 3. Kubernetes Autodiscovery

Instead of hardcoding configurations, we use **Kubernetes Annotations and Labels** to instruct the Agent on how to monitor services.

### Service Tagging (Unified Service Tagging)
All deployments must include these standard labels to correlate Traces, Logs, and Metrics:

```yaml
labels:
  [tags.datadoghq.com/service](https://tags.datadoghq.com/service): "nerp-dashboard" # Service name in APM
  [tags.datadoghq.com/env](https://tags.datadoghq.com/env): "production" # Environment filter
  [tags.datadoghq.com/version](https://tags.datadoghq.com/version): "1.0.0" # Version for deployment tracking

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
