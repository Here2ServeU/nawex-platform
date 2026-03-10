# Splunk HEC (HTTP Event Collector) Configuration

This directory contains the Helm chart for managing the **Splunk HTTP Event Collector (HEC)** integration. Unlike the Universal Forwarder (which ships logs from files), the HEC endpoint allows applications and serverless functions to send data directly to Splunk via HTTP/JSON.

This chart focuses on the **secure provisioning** of HEC tokens and connection details as Kubernetes Secrets, ensuring that sensitive credentials are never hardcoded in application manifests.

## Directory Structure

* **`Chart.yaml`**: Defines the chart metadata.
* **`values.yaml`**: The configuration layer. Defines SRE standards for:
    * **HEC Endpoint:** The centralized URL for the Splunk ingestion tier (e.g., `https://http-inputs-splunk.example.com:8088`).
    * **Token Rotation:** Parameters for updating tokens without downtime.
    * **Ack Enabled:** Configures whether the client waits for Splunk to acknowledge receipt (critical for zero-data-loss guarantees).
* **`templates/`**:
    * `secret.yaml`: Creates the `splunk-hec-config` secret containing the base64-encoded token.
    * `external-name-service.yaml`: Maps the external Splunk URL to an internal Kubernetes Service name (e.g., `splunk-hec.monitoring.svc.cluster.local`), abstracting the destination.

## Core Capabilities & SRE Value

### 1. Secret Management & Compliance
* **Problem:** Developers hardcoding Splunk tokens in their `deployment.yaml` files. If the repo is public, the token is compromised.
* **Solution:** We inject the token as an Environment Variable from a centralized Kubernetes Secret managed by this chart.
* **Impact:** **Credential Hygiene.** We can rotate the Splunk token in one place (this chart), and all 50+ microservices automatically get the new credential upon rollout.

### 2. High-Throughput Ingestion
* **Problem:** Traditional log file tailing is too slow for high-volume serverless or event-driven architectures.
* **Solution:** HEC allows direct, high-speed JSON POSTs to Splunk.
* **Impact:** **Real-Time Visibility.** Latency from "event happening" to "event searchable in Splunk" drops from minutes to milliseconds.

### 3. Network Abstraction
* **Problem:** Changing the Splunk provider (e.g., moving from On-Prem to Splunk Cloud) breaks every application that has the old URL hardcoded.
* **Solution:** Apps send data to the internal `splunk-hec` Service. This service points to the actual external URL.
* **Impact:** **Zero-Touch Migrations.** We can switch the backend destination in this chart, and applications don't even know the IP changed.

## Usage Guide

**To Deploy:**
This chart is typically a dependency for other apps, but can be deployed standalone to provision the secrets.

```bash
helm upgrade --install splunk-hec ./splunk-hec \
  --set splunk.url=[https://inputs.splunk-cloud.com:8088](https://inputs.splunk-cloud.com:8088) \
  --set splunk.token=$SPLUNK_HEC_TOKEN \
  -n monitoring
````

**Developer Usage:**
Developers consume the secret in their deployments:

```yaml
env:
  - name: SPLUNK_HEC_TOKEN
    valueFrom:
      secretKeyRef:
        name: splunk-hec-config
        key: token
  - name: SPLUNK_HEC_URL
    value: "[http://splunk-hec.monitoring.svc.cluster.local:8088](http://splunk-hec.monitoring.svc.cluster.local:8088)"
```

### Talking Point:
> I separated `splunk-hec` into its own chart to solve the **'Secret Sprawl'** problem. Instead of every app team managing their own Splunk credentials, I centralize the HEC token management here. This allows me to rotate tokens instantly for security compliance and gives me a single point of control to point traffic to a different Splunk instance (like during a DR failover) without redeploying a single application.

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
