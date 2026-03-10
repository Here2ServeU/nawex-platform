# OpenTelemetry Collector (OTel)

This directory contains the Helm chart for deploying the **OpenTelemetry Collector**. This component serves as the **Universal Telemetry Agent** for the platform, responsible for receiving, processing, and exporting telemetry data (Traces, Metrics, and Logs).

By standardizing on OTel, we decouple our application instrumentation from our backend storage, ensuring **Vendor Neutrality** and future-proofing the observability stack.

## Directory Structure

* **`Chart.yaml`**: Defines the chart metadata and versioning.
* **`values.yaml`**: The critical configuration layer. Defines the OTel pipeline:
    * **Receivers:** Protocols accepted (e.g., OTLP/gRPC, OTLP/HTTP, Jaeger).
    * **Processors:** Data manipulation rules (e.g., `batch` for compression, `memory_limiter` for stability, `attributes` to scrub sensitive data).
    * **Exporters:** Destinations for the data (e.g., Prometheus for metrics, Jaeger/Splunk for traces).
* **`templates/`**:
    * `daemonset.yaml`: Deploys the collector on every node to capture host metrics and local app traces.
    * `configmap.yaml`: The actual YAML configuration injected into the collector binary.
    * `service.yaml`: Exposes ports (4317 for gRPC, 4318 for HTTP) to the cluster.

## Core Capabilities & SRE Value

### 1. Vendor Agnosticism (Anti-Lock-in)
* **Problem:** Hardcoding a vendor's SDK (e.g., Datadog agent) into application code makes it impossible to switch tools without rewriting 50 microservices.
* **Solution:** Apps send data to *this* OTel Collector in a standard format. The Collector then forwards it to the vendor.
* **Impact:** **Strategic Flexibility.** We can migrate from Datadog to Splunk (or open-source Jaeger) in minutes by updating `values.yaml`, with zero code changes required by developers.

### 2. Unified Telemetry Pipeline
* **Problem:** Fragmented visibility. "Metrics are in Prometheus, logs are in ELK, and traces are in X-Ray."
* **Solution:** The OTel Collector creates a single pipeline that can tag logs with Trace IDs and correlate metrics with specific spans.
* **Impact:** **Rapid Debugging.** Enables engineers to jump seamlessly from a 500-error metric to the exact distributed trace that caused it.

### 3. Cost Control (Sampling & Filtering)
* **Problem:** Storing 100% of traces is prohibitively expensive and mostly useless (99% are "200 OK").
* **Solution:** We configure **Tail Sampling** processors in the Collector to only keep "interesting" traces (errors or high latency).
* **Impact:** **Observability Budget Optimization.** We get high-fidelity data for failures while discarding the noise, saving thousands in storage costs.

## Usage Guide

**To Deploy:**
This chart typically runs as a DaemonSet to collect data from pods on the same node.

```bash
helm upgrade --install otel-collector ./otel-collector -f values.yaml -n monitoring
````

**Developer Usage:**
Developers simply point their application SDKs to the local node:

  * **Endpoint:** `otel-collector.monitoring.svc.cluster.local:4317`
  * **Protocol:** OTLP (gRPC)

### Talking Point:
> I implemented the **OpenTelemetry Collector** because I believe in **'Instrumentation once, send anywhere.'** In my previous roles, I saw how painful it was to rip out proprietary agents when contracts changed. By using this OTel chart, I've future-proofed the platform—we can switch from AWS X-Ray to Jaeger to Honeycomb just by changing a few lines of YAML in this chart, without bothering a single developer.

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
