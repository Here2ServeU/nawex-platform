# Log Correlation & Observability Design

## 1. Overview
This document outlines the architecture for distributed tracing and log correlation within the Express AIOps platform. The goal is to ensure every log entry can be linked to a specific user request and distributed trace, enabling seamless navigation between **Infrastructure Metrics**, **Application Logs**, and **APM Traces** in Datadog and Splunk.

### Objectives
* **Unified Observability:** Link logs to APM traces (`trace_id`, `span_id`).
* **Request Tracking:** End-to-end tracking via `correlation_id` across microservices.
* **Structured Logging:** Enforce JSON format for machine parsing and high-cardinality filtering.

---

## 2. Architecture

The observability pipeline follows a **sidecar** or **daemonset** pattern using FluentBit to decouple log shipping from application logic.

```mermaid
graph LR
    A[Client Request] -->|x-correlation-id| B(Express App)
    B -->|JSON Logs| C{FluentBit}
    C -->|Datadog Plugin| D[Datadog HQ]
    C -->|HEC| E[Splunk]
    
    subgraph "Log Context"
    L1[trace_id]
    L2[span_id]
    L3[correlation_id]
    end
    
    B -.-> L1
    B -.-> L2
    B -.-> L3

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
