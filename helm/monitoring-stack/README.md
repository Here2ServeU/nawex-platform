# Prometheus & Grafana Monitoring Suite

This directory contains the Helm chart for deploying the core **Metrics & Alerting Stack** (Prometheus, Grafana, Alertmanager, and Node Exporter).

While logs (Splunk) and traces (OpenTelemetry) provide deep debugging context, this stack provides the **"Pulse"** of the platform—instant, high-level visibility into infrastructure health and application performance.

## Directory Structure

* **`Chart.yaml`**: Defines the chart metadata and declares dependencies (often wrapping the community `kube-prometheus-stack`).
* **`values.yaml`**: The configuration layer. Defines SRE standards for:
    * **Retention:** Configures how long metrics are kept (e.g., 15 days) before being discarded or downsampled.
    * **Persistence:** Enables Persistent Volumes (PVs) to ensure historical metric data survives pod restarts.
    * **Resource Limits:** CAPS memory usage for Prometheus to prevent OOM (Out of Memory) kills during high-cardinality spikes.
* **`templates/`**: Custom overrides and additional resources.
    * `dashboards/`: ConfigMaps containing JSON definitions for standard "Golden Signal" dashboards.
    * `alert-rules.yaml`: PrometheusRule definitions for firing alerts on critical conditions (e.g., `HighErrorRate`, `NodeDown`).

## Core Capabilities & SRE Value

### 1. The "Single Pane of Glass"
* **Problem:** Engineers have to SSH into servers or check 5 different consoles to see if the system is up.
* **Solution:** We deploy pre-configured **Grafana Dashboards** as Code.
* **Impact:** Immediate situational awareness. A developer can look at one screen and see CPU, Memory, Request Rate, and Error Rate across the entire cluster.

### 2. Intelligent Alerting (Signal vs. Noise)
* **Problem:** "Pager Fatigue." Getting woken up at 3 AM because a CPU spiked for 2 seconds.
* **Solution:** We implement **Alertmanager** with smart grouping and "wait" windows (e.g., "CPU must be >90% for *5 minutes*").
* **Impact:** Actionable Alerts. If the pager goes off, it means there is a real problem that requires human intervention.

### 3. Infrastructure Vital Signs
* **Problem:** Application performance degrades, but no one knows if it's bad code or a bad server.
* **Solution:** **Node Exporter** and **Kube State Metrics** run on every node, capturing hardware-level telemetries (Disk I/O, Network saturation).
* **Impact:** Rapid Root Cause Analysis. We can instantly correlate "App is slow" with "Node 4 has a noisy neighbor stealing all the I/O."

## Usage Guide

**To Deploy or Update:**
This chart is designed for GitOps (ArgoCD), but can be tested manually:

```bash
helm upgrade --install monitoring-stack ./monitoring-stack -f values.yaml -n monitoring
````

**Key Dashboards Included:**

  * **Cluster Overview:** Total capacity, node health, and pod density.
  * **USE Method:** Utilization, Saturation, and Errors for every microservice.
  * **Kubelet Health:** API Server latency and controller manager status.


### Talking Point:
> I use this `monitoring-stack` to ensure we have 'eyes on glass' from Day 1. While I use Splunk for deep log analysis, I rely on **Prometheus** for real-time alerting because it's fast and cheap. I also treat my Grafana dashboards as code—they are stored in this Git repo (in `templates/`), so if we accidentally delete a dashboard, I can restore it in seconds.
