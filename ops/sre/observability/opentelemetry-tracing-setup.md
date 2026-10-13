# OpenTelemetry Tracing Implementation Guide

## 1. Overview
This document defines the standard for distributed tracing within the Express AIOps Platform. We utilize **OpenTelemetry (OTel)** to instrument application services in a vendor-neutral manner, enabling us to export telemetry data to multiple backends (Datadog APM, Grafana Tempo) without changing application code.

### Goals
* **Vendor Neutrality:** Decouple instrumentation from the backend analysis tool.
* **End-to-End Visibility:** Trace requests from the ingress controller down to database queries.
* **Standardization:** Enforce consistent `service.name` and resource attributes across all microservices.

---

## 2. Architecture

We employ a **Collector-based architecture**. Applications do not send traces directly to backends; instead, they send OTLP (OpenTelemetry Protocol) data to a central OpenTelemetry Collector, which processes and exports the data.

```mermaid
graph LR
    subgraph "Kubernetes Cluster"
        A[Express App] -->|OTLP/gRPC| B(OTel Collector)
        B -->|Process/Batch| B
    end
    
    B -->|OTLP| C[Grafana Tempo]
    B -->|Datadog Exporter| D[Datadog APM]

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
