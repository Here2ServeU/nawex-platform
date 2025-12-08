# Kafka & Zookeeper High-Availability Chart

This directory contains the Helm chart for deploying a production-ready **Apache Kafka** cluster (coordinated by **Zookeeper**). This infrastructure serves as the central nervous system of the AIOps platform, acting as a durable message bus for all high-volume telemetry data (logs, traces, metrics).

## Directory Structure

* **`Chart.yaml`**: Defines the chart metadata and declares the dependency on the official Bitnami Kafka chart (sub-chart pattern).
* **`values.yaml`**: The configuration layer. Defines SRE standards for:
    * **Persistence:** Storage class definitions (SSD) for high-throughput I/O.
    * **Retention Policies:** How long logs are kept (e.g., 7 days) before rotation to manage disk costs.
    * **Replicas:** Configures a default replication factor of 3 to ensure zero data loss if a node fails.
* **`templates/`**: Custom overrides and additional resources.
    * `topics-job.yaml`: A Kubernetes Job that automatically creates essential topics (e.g., `app-logs`, `otel-traces`) upon installation, preventing "topic not found" errors.

## Core Capabilities & SRE Value

### 1. Data Durability & Buffering
* **Problem:** "Thundering Herd." During a massive outage, millions of error logs are generated instantly. If sent directly to the database (Elasticsearch/Splunk), the database crashes.
* **Solution:** Kafka acts as a **Shock Absorber**. It accepts millions of messages per second and writes them to disk. The backend consumers can then process them at their own safe pace.
* **Impact:** Prevents **Telemetry Data Loss**. We capture the critical logs *during* the crash, which is when we need them most.

### 2. Decoupled Architecture
* **Problem:** Tightly coupled systems where the Application must know the IP address of the Logging Backend.
* **Solution:** Producers (Apps) only know about Kafka. Consumers (AIOps Engine, Splunk Forwarder) only know about Kafka. They never talk to each other.
* **Impact:** **Evolutionary Architecture**. We can swap out the backend (e.g., move from Splunk to Datadog) without rewriting a single line of application code.

### 3. High Availability (HA)
* **Problem:** Single points of failure in the messaging layer.
* **Solution:** The chart deploys a 3-node Kafka cluster and a 3-node Zookeeper ensemble with **PodAntiAffinity**.
* **Impact:** Ensures the messaging bus survives the loss of an entire Kubernetes node or availability zone.

## Usage Guide

**To deploy or upgrade:**
This chart uses a dependency pattern. First, download the sub-charts:

```bash
helm dependency build ./kafka-zookeeper
````

Then deploy via Helm or ArgoCD:

```bash
helm install aiops-bus ./kafka-zookeeper -f values.yaml
```

**Key Topics Created by Default:**

  * `telemetry.logs.raw` (Retention: 24h)
  * `telemetry.metrics.raw` (Retention: 2h)
  * `aiops.alerts.processed` (Compacted)

### Interview Talking Point:
> I included Kafka in my architecture because at scale, **synchronous logging is a death sentence**. I use this Kafka chart to decouple my services from my analysis tools. It acts as a durable buffer—if my AIOps engine goes down for maintenance, Kafka holds all the data until it comes back up. No data is ever lost.
