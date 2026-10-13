# Golden Platform — Master Guide

> This guide is a compiled snapshot of documents from across the repository; some sections predate the v2 layout. Where it disagrees with the source file, the source file wins. Every number is either reproducible or labelled as a target — see the [claims register](CLAIMS.md). Quantum methods are not implemented ([research note](architecture/06-quantum-optimization-layer.md)).


---


## Source: README.md

# Golden Platform: Predictive Clinical Safety Platform

## Executive Summary: Bridging the Gap Between AI and Infrastructure

The **Golden Platform** is an enterprise-grade ecosystem designed for high-availability healthcare environments. By integrating **Deep Learning (LSTM/TCN)** with per-cloud landing zones and a multi-cloud active-active *design target*, the platform aims to move infrastructure for critical [robotics telemetry streams](../src/golden/robotics) from reactive to predictive. The API availability SLO objective is 99.9%; no production uptime has been measured.

## Architectural Excellence (Golden Project Standard)

This project utilizes the **Golden Platform-Golden-Project** structure to support SOC 2 and [HIPAA-mapped](compliance/01-hipaa-compliance-mapping.md) auditability (mappings, not certifications).

* **[Core AI Brain](../src/golden/ai)**: Dual-model ensemble (LSTM for long-range trends; TCN for high-frequency anomalies). Precision targets are listed in [CLAIMS.md](CLAIMS.md); models are trained on synthetic data.
* **[Multi-Cloud Topology](architecture/03-infrastructure-topology.md)**: Global orchestration across **AWS, Azure, GCP, and OCI** using modular [Terraform](../deploy/terraform) and [GitOps](../deploy/gitops).
* **[Resilience Engine](architecture/05-active-active-resilience.md)**: [Predictive failover logic](architecture/04-predictive-reliability-framework.md) with a < 30 s RTO *target* (not measured; cross-cloud failover not implemented).

## Ph.D. Research Implementation

The platform is a reference implementation of AI research in healthcare resilience (synthetic data; not deployed in production):

* **Agentic Safety Mediation**: Real-time kinematic telemetry analysis at the [Robotics Edge](../src/golden/robotics).
* **MLOps Lifecycle**: Drift-triggered retraining and a gated model registry (`golden model`); [GCP Vertex AI](architecture/03-infrastructure-topology.md) offload is a design option.

## Compliance & Governance

Designed to be mapped to **HIPAA**, **SOC 2**, and **French HDS** (not certified).

* **[Audit Logging Policy](compliance/03-audit-logging-policy.md)**: Tamper-evident, hash-chained decision logs; WORM storage is a deployment requirement.
* **[Disaster Recovery Plan](compliance/04-disaster-recovery-plan.md)**: Active-Active business continuity plan with target RTO/RPO.

---

### Navigation

* **[Architecture Deep Dives](architecture)**
* **[Compliance Mapping](compliance)**
* **[Operator Guides](guides)**
* **[Robotics Demo](robotics/README.md)**

---

## Operational Quickstart (Interview-Ready)

* **[Quickstart Guide](guides/quickstart.md)**
* **[Interview Demo Runbook](guides/interview-demo.md)**
* **[Troubleshooting (All Domains)](guides/troubleshooting.md)**

### One-Command Bootstrap

```bash
make bootstrap
```

### One-Click Demo Launcher

```bash
make demo
```

### Start Services

```bash
make up
golden orchestrate
```

### Demo Chaos + Recovery

```bash
scripts/tools/chaos_demo.sh
scripts/tools/heal.sh
```



---


## Source: src/golden/ai/README.md

# AIOps & Predictive Resilience Engine (/ai)

## The Nervous System of the Express Platform
This directory contains the **Autonomous Reliability Agents** and **Deep Learning Models** that power the platform's governed self-healing: every action passes the `ActionGovernor` and the default autonomy mode is `dry_run` (`golden security status`). It transforms raw telemetry into actionable remediation plans using a continuous *Observe-Analyze-Plan-Execute* control loop.

---

## 1. Autonomous Agent Architecture
The system is composed of four decoupled agents, coordinated by a central **Orchestrator** (`agents/orchestrator.py`).

| Agent | Role | Logic & Responsibilities |
| :--- | :--- | :--- |
| **Observer** | *The Eyes* | Collects real-time telemetry (Latency, CPU, Error Rates). Supports pluggable adapters for Prometheus and CloudWatch. |
| **Analyzer** | *The Brain* | Detects anomalies using a hybrid approach:<br>1. **Deterministic:** Static thresholds (e.g., Latency > 200ms).<br>2. **Predictive:** PyTorch models forecasting SLI violations. |
| **Planner** | *The Logic* | Maps identified risks to remediation strategies using a Rule-Based Engine. Generates an audit trail (`plan_id`, reasoning). |
| **Executor** | *The Hands* | Safely applies changes to infrastructure.<br>• **Dry Run:** Simulates actions for safety.<br>• **Active:** Executes real `kubectl` or Terraform commands.<br>• **Safety Rails:** Prevents cascading failures with strict action limits. |

---

## 2. Predictive Modeling (PyTorch)
Located in `models/`, we utilize custom deep learning models to predict Service Level Objective (SLO) violations before they impact users.

* **LSTM (Long Short-Term Memory):** Specialized for detecting temporal dependencies in sequential time-series data (e.g., CPU trends).
* **TCN (Temporal Convolutional Network):** Uses dilated convolutions to capture long-range patterns with higher training efficiency than RNNs.

**Key Files:**
* `models/tcn_model.py`: TCN implementation with causal padding.
* `models/lstm_model.py`: PyTorch LSTM implementation with state persistence.

---

## 3. Data Pipelines & Log Intelligence
Located in `pipelines/`, this module handles the preprocessing of high-volume telemetry data.

* **Log Clustering (`log-cluster.py`):** Uses unsupervised learning (K-Means/DBSCAN) to group millions of raw log lines into distinct "patterns."
    * **SRE Value:** Reduces **Alert Fatigue** by compressing 10,000 "Connection Failed" logs into a single "Database Connectivity Issue" event.

---

## 4. Remediation Engine
Located in `remediation/`, the remediation logic is **declarative** and **dynamic**. You can define new self-healing rules without changing Python code.

**Configuration:** `remediation/remediation_rules.yaml`

```yaml
rules:
  - id: "rule-001"
    trigger: "latency_risk"
    level: "high"
    action: "scale_up_replicas"
    params:
      target: "frontend-service"
      replicas: 5
````

### Interview Talking Point

> I designed the `ai/` directory to be modular. The **Agents** handle the lifecycle, but the intelligence comes from the **Models** and **Pipelines**. Recently, I added `log-cluster.py` to the pipelines folder to solve the 'Log Spam' problem—it uses ML to group similar logs so the AIOps engine isn't overwhelmed by noise during an outage.


---


## Source: src/golden/ai/agents/README.md

# Autonomous Reliability Control Plane

This directory implements the **Self-Healing Control Loop** for the platform. It is architected as a modular, autonomous multi-agent system designed to maintain system stability through continuous feedback and automated remediation.

The core design follows the **MAPE-K** feedback loop pattern, decoupling the observation of system state from the execution of remediation logic.

## System Architecture

### 1. Orchestration Layer
* **File:** `orchestrator.py`
* **Function:** Serves as the central runtime controller. It initializes the agent lifecycle, manages the shared knowledge base (state), and enforces the synchronous or asynchronous ticking of the control loop. It ensures data consistency as state transitions from observation to execution.

### 2. The Agent Fleet
The logic is distributed across four specialized agents, each responsible for a distinct phase of the autonomic cycle:

#### Observer Agent (`agents/observer_agent.py`)
* **Phase:** **Monitor**
* **Responsibility:** Ingests high-velocity telemetry streams from the observability backend (Prometheus/Splunk). It handles data normalization and feature extraction, converting raw metrics into structured vectors suitable for analysis.

#### Analyzer Agent (`agents/analyzer_agent.py`)
* **Phase:** **Analyze**
* **Responsibility:** Performs anomaly detection and root cause analysis. It utilizes statistical models and machine learning inference (referenced in `../models`) to evaluate the normalized data against dynamic baselines. It distinguishes between transient noise and true regression signals.

#### Planner Agent (`agents/planner_agent.py`)
* **Phase:** **Plan**
* **Responsibility:** The decision engine. Upon receiving an anomaly signal, it queries the `agent_config.yaml` policies to determine the optimal remediation strategy. It generates a specific execution plan (e.g., vertical scaling vs. horizontal scaling) based on the severity and confidence score of the analysis.

#### Executor Agent (`agents/executor_agent.py`)
* **Phase:** **Execute**
* **Responsibility:** The actuation layer. It interfaces with the infrastructure APIs (Kubernetes, AWS SDK) to apply the remediation plan. It implements strict **safety rails**, including rate limiting and dry-run capabilities, to prevent hysteresis or destructive cascading actions.

## Configuration & Policy

**File:** `agent_config.yaml`
This declarative configuration file acts as the **Policy Controller**. It defines:
* **Detection Sensitivity:** Thresholds for the Analyzer's inference models.
* **Actuation Budgets:** Safety limits on the number of automated actions allowed per time window.
* **Allowlists:** Explicit permissions for what infrastructure mutations the Executor can perform.

## Execution

The system is designed to run as a persistent daemon or a scheduled Kubernetes CronJob.

```bash
# Initialize the control loop
python orchestrator.py --config agent_config.yaml --mode active
````


---


## Source: src/golden/ai/models/README.md

# Predictive Inference Models

This directory contains the PyTorch implementations of the deep learning architectures used by the **Analyzer Agent**. These models are designed specifically for high-dimensional time-series forecasting, enabling the platform to predict Service Level Objective (SLO) violations before they occur.

The repository currently implements two distinct architectures to handle different types of temporal telemetry patterns.

## Model Architectures

### 1. Long Short-Term Memory (LSTM)
* **File:** `lstm_model.py`
* **Architecture:** A Recurrent Neural Network (RNN) variant designed to overcome the vanishing gradient problem.
* **Use Case:** **Sequential Dependency Analysis.**
* **Technical Detail:** Utilizing memory cells and gating mechanisms (input, output, forget gates), this model excels at capturing long-term dependencies in telemetry streams. It is particularly effective for metrics with strong seasonality or historical context, such as daily traffic spikes or gradual memory leaks.

### 2. Temporal Convolutional Network (TCN)
* **File:** `tcn_model.py`
* **Architecture:** A sequence modeling architecture based on 1D causal dilated convolutions.
* **Use Case:** **High-Frequency Anomaly Detection.**
* **Technical Detail:** Unlike RNNs, the TCN processes sequences in parallel (non-autoregressive training) and uses dilated convolutions to achieve an exponentially large receptive field. This allows it to detect anomalies in high-frequency data streams (e.g., 10ms CPU polls) with significantly lower inference latency and training time compared to LSTMs.

## Integration & Lifecycle

These models are not executed standalone but are instantiated by the **Analyzer Agent** (`../agents/analyzer_agent.py`) during the initialization phase.

* **Training:** Models are trained offline on historical metric data (CPU, Memory, Request Latency) to learn the "baseline" behavior of the application.
* **Inference:** During runtime, the models ingest a sliding window of normalized real-time metrics from the **Observer Agent**.
* **Output:** The models output a probability score (0.0 - 1.0) indicating the likelihood of an upcoming SLO breach, which the **Planner Agent** uses to trigger remediation.

## Usage

To test a model architecture in isolation (dry-run):

```bash
# Verify model structure and forward pass
python lstm_model.py --verify
````


---


## Source: src/golden/ai/pipelines/README.md

# MLOps & Data Processing Pipelines

This directory contains the end-to-end data engineering and model training pipelines that power the AIOps engine. It implements a robust **ETL (Extract, Transform, Load)** framework specifically designed for high-velocity time-series telemetry and unstructured log data.

These scripts bridge the gap between raw infrastructure signals and the deep learning models located in `../models`, ensuring data consistency between offline training and online inference.

## Pipeline Architecture

### 1. Data Ingestion & Feature Engineering
* **Files:** `data_loader.py`, `feature_engineering.py`
* **Function:** Implements the **Data Preprocessing Layer**.
* **Technical Detail:** * **Ingestion:** `data_loader.py` handles connections to the TSDB (Prometheus/InfluxDB) to fetch historical training data.
    * **Transformation:** `feature_engineering.py` applies critical transformations such as **Z-Score Normalization** (to handle scale differences between CPU % and Memory Bytes) and **Sliding Window generation** (converting flat time-series into 3D tensors `[batch_size, seq_len, features]` required for LSTM/TCN input).

### 2. Model Training Loops
* **Files:** `train_lstm.py`, `train_tcn.py`
* **Function:** The **Model Production Layer**.
* **Technical Detail:** These scripts manage the supervised learning lifecycle. They handle:
    * **Hyperparameter Tuning:** Configuration of learning rates, batch sizes, and dropout layers.
    * **Validation:** Splitting datasets into train/test/validation sets to prevent overfitting.
    * **Serialization:** Saving the trained model weights (`.pth` files) and the scaler artifacts so they can be loaded by the inference agents.

### 3. Inference Engines
* **File:** `detect_anomalies.py`
* **Function:** The **Metric Anomaly Detection** runtime.
* **Technical Detail:** This script loads the trained models and performs forward passes on live data streams. It calculates the **Reconstruction Error** (for autoencoders) or **Prediction Error** (for forecasting models); if the error exceeds a dynamic threshold, an anomaly is flagged.

* **File:** `log-cluster.py`
* **Function:** The **Log Intelligence** runtime.
* **Technical Detail:** Implements **Unsupervised Learning** (K-Means / DBSCAN) on unstructured text data. It uses TF-IDF vectorization to convert raw log lines into numerical space, grouping semantically similar logs (e.g., "Connection timeout" vs "Connection refused") to drastically reduce alert volume.

## Operational Workflow

The pipeline follows a strict **Data-Centric AI** workflow:

1. **Extraction:** `data_loader.py` pulls raw metrics.
2. **Vectorization:** `feature_engineering.py` normalizes and shapes the data.
3. **Training:** `train_tcn.py` produces a model artifact.
4. **Deployment:** `detect_anomalies.py` loads the artifact for real-time scoring.

## Usage

To retrain the TCN model on the latest dataset:

```bash
python train_tcn.py --epochs 50 --batch_size 64 --data ./data/metrics.csv
````

### Interview Talking Point
> "I built this pipeline directory to enforce MLOps best practices. A common pitfall in AIOps is 'training-serving skew,' where the data used to train the model looks different from live production data. By centralizing the logic in `feature_engineering.py`, I ensure that the exact same normalization code runs during both `train_lstm.py` (offline training) and `detect_anomalies.py` (online inference). I also implemented `log-cluster.py` to move beyond simple metric thresholds—it allows the system to understand *semantic* patterns in logs, reducing thousands of noisy lines into a single, actionable root cause.


---


## Source: src/golden/ai/remediation/README.md

# Automated Remediation Engine

This directory contains the logic for the **Execution Phase** of the AIOps control loop. It serves as the actuation layer that translates high-level decisions from the Planner Agent into specific, low-level infrastructure commands (e.g., Kubernetes API calls, Terraform applies, or script executions).

The design prioritizes safety and determinism, ensuring that automated actions do not cause cascading failures or "flapping" states.

## System Architecture

### 1. The Execution Core
* **File:** `remediation_engine.py`
* **Function:** The runtime execution driver.
* **Technical Detail:** This script acts as a safe wrapper around infrastructure APIs. It accepts a standard `Plan` object and matches it against the defined rules. It implements critical SRE safety patterns:
    * **Idempotency:** Ensures that applying the same action multiple times yields the same result (e.g., "Scale to 5 replicas" is safe to repeat; "Add 1 replica" is not).
    * **Dry-Run Capability:** Allows the system to simulate remediation actions in logs without mutating the production state.
    * **Error Handling:** Graceful fallbacks if the underlying cloud provider API is unresponsive.

### 2. Policy-as-Code Configuration
* **File:** `remediation_rules.yaml`
* **Function:** The declarative knowledge base for self-healing.
* **Technical Detail:** Decouples the remediation *logic* (Python) from the remediation *policy* (YAML). This allows SREs to add new self-healing capabilities (e.g., "Restart Pod on Memory Leak") without redeploying the engine code.

## Remediation Workflow

The engine follows a strict **Trigger-Action-Validation** flow:

1. **Trigger:** The engine receives a `RemediationPlan` from the Planner Agent containing a `diagnosis_id` (e.g., `HIGH_LATENCY_FRONTEND`).
2. **Lookup:** It scans `remediation_rules.yaml` to find the matching policy.
3. **Constraints Check:** It verifies if the action is currently allowed (e.g., not during a blackout window, and not exceeding the rate limit).
4. **Execution:** It invokes the specific handler (e.g., `scale_deployment(service, count)`).
5. **Audit:** The action is logged with a correlation ID for post-incident review.

## Configuration Example

Rules are defined declaratively to support dynamic reloading:

```yaml
rules:
  - id: "cpu-saturation-recovery"
    description: "Horizontal scaling when CPU exceeds safety thresholds"
    trigger_condition: "cpu_usage > 85%"
    action:
      type: "kubernetes_scale"
      target_resource: "deployment/frontend"
      parameters:
        min_replicas: 3
        max_replicas: 10
        step_size: 2
    safety_rails:
      cooldown_period: "300s"
      max_daily_actions: 5
````

## Usage

The engine is typically invoked by the Orchestrator, but can be run manually for testing rules:

```bash
# Test a specific rule against a dry-run target
python remediation_engine.py --rule cpu-saturation-recovery --dry-run
```

### Interview Talking Point
> I architected the `remediation` module to separate **Mechanism** from **Policy**. The `remediation_engine.py` is the mechanism—it knows *how* to scale a pod or restart a service. The `remediation_rules.yaml` is the policy—it decides *when* that should happen. This separation is critical for a Senior SRE role because it allows me to safely enable automation incrementally. We can deploy the code today but keep the rules commented out, or run them in 'Dry Run' mode to build confidence before letting the AI touch production.


---


## Source: apps/workload/README.md

# Express.js Reference Microservice

This directory contains the source code for the **Reference Workload** of the platform. It is a Node.js/Express application designed specifically to demonstrate **Observability-Driven Development**.

Unlike a standard "Hello World" app, this microservice is heavily instrumented to emit "Golden Signals" (Latency, Traffic, Errors, Saturation) and includes chaos endpoints to simulate production failures.

## Directory Structure

* **`src/`**: Application source code.
    * `app.js`: Main entry point initializing the Express server.
    * `tracing.js`: **OpenTelemetry SDK** configuration (must run before any other module).
    * `routes/`: API endpoints.
* **`Dockerfile`**: Multi-stage build definition for creating a lightweight, secure container image (Distroless or Alpine).
* **`package.json`**: Defines dependencies, including `prom-client` (metrics) and `@opentelemetry/sdk-node` (traces).

## Core Capabilities & SRE Value

### 1. Built-in Observability
* **Feature:** The app automatically exposes a `/metrics` endpoint for Prometheus scraping.
* **SRE Value:** **Zero-Touch Instrumentation.** New developers don't need to learn how to monitor their code; the base framework handles request duration buckets and error counters automatically.

### 2. Distributed Tracing (OpenTelemetry)
* **Feature:** Every incoming HTTP request is assigned a `trace-id`. If this service calls a database or another API, the context is propagated.
* **SRE Value:** **Full-Stack Visibility.** We can visualize the entire request journey in Jaeger/Splunk, identifying exactly which microservice is the bottleneck.

### 3. "Chaos" Endpoints
* **Feature:** The app includes specific routes to simulate bad behavior:
    * `GET /error`: Intentionally throws a 500 Internal Server Error.
    * `GET /slow`: Sleeps for 2 seconds before responding (simulating high latency).
    * `GET /leak`: Simulates a memory leak.
* **SRE Value:** **Resilience Testing.** These endpoints are used by the `sre/chaos` scripts to validate that our alerts fire correctly when things go wrong.

## Local Development

**Prerequisites:** Node.js v18+

```bash
# 1. Install dependencies
npm install

# 2. Start the app (with tracing enabled)
npm start
````

**Testing Endpoints:**

  * Health Check: `curl http://localhost:8080/health`
  * Metrics: `curl http://localhost:8080/metrics`
  * Simulate Error: `curl http://localhost:8080/error`

## Docker Usage

The `Dockerfile` is optimized for production (caching layers, non-root user).

```bash
# Build
docker build -t aiops-app .

# Run
docker run -p 8080:8080 aiops-app
```

### Talking Point
> I wrote this `app` to be the 'guinea pig' for my platform. It’s not just a web server; it’s a **telemetry generator**. I built in specific endpoints like `/slow` and `/error` so I could trigger failures on demand and verify that my AIOps engine detects them within seconds. This proves the feedback loop between the Application layer and the Infrastructure layer.


---


## Source: docs/README.md

# Engineering Knowledge Base & Architecture

This directory serves as the **Single Source of Truth** for the platform's architectural design, decision records, and operational guides.

Following the **"Docs-as-Code"** methodology, all documentation is version-controlled alongside the application code. This ensures that the documentation evolves in lockstep with the infrastructure, preventing the common "stale wiki" problem.

## Directory Structure

### Architectural Deep Dives
These documents detail the implementation strategies for our observability backends.

* **File:** [`splunk-observability.md`](guides/splunk-observability.md)
    * **Focus:** **Log Aggregation Strategy.**
    * **Key Decisions:** Universal Forwarder vs. HEC, Index Segmentation (`main` vs. `audit`), and Data Retention policies.

* **File:** [`observability/README.md`](../observability/README.md) (Prometheus/Grafana stack, metric contract, alert routing)
    * **Focus:** **Open Source Metrics & Alerting.**
    * **Key Decisions:** "Pull" model architecture, `ServiceMonitor` CRD usage, and "Dashboards-as-Code" lifecycle management.

* **File:** [`deploy/gitops/argocd/app-datadog.yaml`](../deploy/gitops/argocd/app-datadog.yaml) and [`ops/sre/observability/datadog-apm-setup.md`](../ops/sre/observability/datadog-apm-setup.md)
    * **Focus:** **Unified SaaS Monitoring.**
    * **Key Decisions:** Agent-based collection (DaemonSet), APM trace sampling rates, and Cost Management (custom metrics filtering).

* **File:** [`deploy/gitops/argocd/app-dynatrace.yaml`](../deploy/gitops/argocd/app-dynatrace.yaml) and [`architecture/advanced-observability.md`](architecture/advanced-observability.md)
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

### 1\. Create New File: `docs/splunk-observability.md`

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
* **Security:** Tokens are managed via Kubernetes Secrets (see `deploy/helm/splunk-hec/templates/secret.yaml`) and rotated quarterly.

### 3. Index Segmentation (Security & Compliance)
* **Strategy:** We segregate data into distinct indexes based on sensitivity and retention requirements.
    * **`main` Index:** Application logs. Retention: 30 days. Accessible by all developers.
    * **`audit` Index:** Authentication logs, sudo commands, and K8s API audit trails. Retention: 1 year (Cold Storage). Accessible only by Security/SRE.
    * **`pci` Index:** Logs from the payment gateway namespace. Strict access controls applied.

### 4. Data Retention & Lifecycle
* **Policy:** "Hot" storage for 7 days (NVMe SSD) for fast searching, moving to "Cold" storage (S3-backed) for long-term compliance.
* **Impact:** Balances search performance with storage costs.
```

-----

### 2\. Create: `docs/prometheus-grafana.md`

*Action: Create this new file in the `docs/` folder.*

```markdown
# Prometheus & Grafana Architecture

## Overview
This document outlines the **Metrics-First** observability strategy using the cloud-native Prometheus stack. While Splunk handles logs, Prometheus provides the high-speed, real-time "heartbeat" of the cluster.

## Architecture Decisions

### The "Pull" Model
Unlike the "Push" model used by Datadog/Splunk agents, Prometheus **scrapes** metrics from targets.
* **Decision:** We use the `ServiceMonitor` Custom Resource Definition (CRD).
* **Why:** It allows development teams to define *how* their app should be scraped (port, path, interval) alongside their application code, adhering to self-service principles.

### High Availability (Thanos Integration)
* **Challenge:** Prometheus is stateful and difficult to scale horizontally.
* **Solution:** We deploy **Thanos Sidecars** to upload old metric blocks to Object Storage (S3/GCS).
* **Impact:** Enables unlimited retention and a global query view across multiple clusters without bloating local disk.

### Dashboards as Code
* **Policy:** No manual edits in the Grafana UI.
* **Workflow:** Dashboards are defined as JSON in the `deploy/helm/monitoring-stack/dashboards` folder.
* **Automation:** A sidecar container watches that folder and calls the Grafana API to reload changes instantly.
```

-----

### 3\. Create: `docs/datadog-observability.md`

*Action: Create this new file in the `docs/` folder.*

```markdown
# Datadog Unified Observability

## Overview
This document details the integration of **Datadog** as our primary SaaS observability platform for Application Performance Monitoring (APM) and Infrastructure correlation.

## Architecture Decisions

### The Unified Agent (DaemonSet)
* **Decision:** We deploy the Datadog Agent as a DaemonSet on every node.
* **Why:** It automatically collects host-level metrics (CPU/Mem), container logs, and network traces without sidecars.
* **Config:** Managed via the `deploy/helm/datadog` chart using `values.yaml` overrides for different environments.

### APM & Trace Sampling
* **Challenge:** Ingesting 100% of traces is cost-prohibitive.
* **Strategy:** We utilize **Tail-Based Sampling** logic.
    * **Keep:** All traces with `error=true` or `latency > 2s`.
    * **Drop:** 99% of successful health checks (`200 OK`).

### Tagging Strategy (Unified Service Tagging)
* **Policy:** Every resource must possess three standard tags: `env`, `service`, and `version`.
* **Enforcement:** Validated by the OPA Gatekeeper policy in the `deploy/gitops/policies` directory.
* **Value:** Enables "Pivot" navigation in Datadog (jumping from Logs -> Metrics -> Traces for a specific version).
```

-----

### 4\. Create: `docs/dynatrace-intelligence.md`

*Action: Create this new file in the `docs/` folder.*

```markdown
# Dynatrace & Davis AI Integration

## Overview
This document covers the **Dynatrace** implementation, specifically focusing on its use for **Automated Root Cause Analysis (RCA)** via the Davis AI engine.

## Architecture Decisions

### Operator-Based Injection
* **Decision:** We use the Dynatrace Operator (`dynatrace-operator`) rather than manual OneAgent installation.
* **Why:** It utilizes a MutatingWebhook to automatically inject the OneAgent loader into application pods at runtime.
* **Impact:** Zero-touch instrumentation. Developers do not need to add libraries to their Dockerfiles.

### PurePath Distributed Tracing
* **Concept:** Dynatrace captures 100% of transactions (PurePaths) without sampling at the agent level.
* **Usage:** Used primarily for deep-dive debugging of complex microservice interactions that span hybrid clouds (e.g., On-Prem Database -> GKE Microservice).

### Problem Detection Profiles
* **Config:** Custom alerting profiles are defined in `deploy/helm/dynatrace/profiles`.
* **Tuning:** We have tuned Davis AI to ignore "frequent but harmless" warnings (like transient high CPU during startup) to reduce alert fatigue.
```

-----

#### Interview Talking Point
"I documented all four major platforms (Splunk, Prometheus, Datadog, Dynatrace) in my docs/ folder to demonstrate Tool Agnosticism. In my experience, large organizations rarely have just one tool—they might use Prometheus for cheap metrics, Splunk for security logs, and Dynatrace for AIOps. As a Senior SRE, my job isn't to be a fanboy of one tool, but to architect a platform that can integrate any of them based on business cost/value requirements."


---


## Source: docs/architecture/01-high-level-architecture.md

# 01: High-Level Platform Architecture

## Executive Overview

The **Golden Platform** is a specialized ecosystem designed to bridge the gap between autonomous systems and enterprise-grade infrastructure resilience. By integrating predictive machine learning models with real-time telemetry, the platform is designed for high availability of critical **healthcare** and **fintech** applications. The API availability SLO objective is 99.9% ([`slo_rules.yml`](../observability/prometheus/rules/slo_rules.yml)); no production uptime has been measured.

## Core Architectural Pillars

1. **Predictive Intelligence**: Utilizing [LSTM and TCN models](../src/golden/ai) to forecast infrastructure failures, robotic kinematic anomalies, and financial transaction irregularities before they manifest.
2. **Governed Remediation**: A remediation loop (observe → analyze → plan → execute, gated by the `ActionGovernor`) powered by [GitOps](../deploy/gitops) and custom SRE controllers that re-provision resources based on risk probability scores.
3. **Regulatory Alignment**: [HIPAA, SOC 2, PCI-DSS, and SOX](compliance/01-hipaa-compliance-mapping.md) control mappings (not certifications), with security scanning and policy gates in CI/CD.

## Functional Components

| Layer | Component | Description |
| --- | --- | --- |
| **Inference** | [AI Brain](../src/golden/ai) | Deep learning engine processing time-series data for anomaly and fraud detection. |
| **Telemetry** | [Robotics Collector](../src/golden/robotics) | High-fidelity data ingestion from edge-based clinical devices. |
| **Fintech** | [Transaction Engine](/src/golden/ai/pipelines/detect_fraud.py) | Real-time transaction monitoring, fraud scoring, and payment reliability assurance. |
| **Orchestration** | [Multi-Cloud IaC](../deploy/terraform) | Per-cloud landing zones for EKS, AKS, GKE and OKE (each deployed independently; no cross-cloud traffic routing yet). |
| **Operations** | [SRE Framework](../ops/sre) | SLO-driven alerting and automated incident response playbooks. |

## Industry-Specific Value

### Healthcare
Aims to reduce Mean Time to Detection (MTTD) by identifying statistical drift in kinematic telemetry before it becomes downtime. MTTD reduction has not been measured.

### Fintech
Ensures transaction integrity and payment system resilience through real-time fraud detection, automated payment gateway failover, and continuous PCI-DSS compliance monitoring. The design target for transaction processing is sub-100 ms; end-to-end latency under load has not been measured (see [CLAIMS.md](CLAIMS.md)).

---

### Implementation Instructions

1. Create the file `docs/architecture/01-high-level-architecture.md`.
2. Paste the content above.
3. Update the hyperlinks to match the specific sub-directories in your repository for perfect navigation.


---


## Source: docs/architecture/02-data-flow-diagrams.md

# Data Flow Architecture: Predictive Healthcare AIOps

## Executive Summary

This architecture integrates **Agentic Clinical Safety** with a **High-Availability AIOps Plane**. By utilizing dual-model inference (LSTM/TCN), the platform is designed to predict kinematic anomalies in robotics telemetry before they result in clinical failure and to trigger governed, GitOps-driven remediation.

> Scope note: the diagram shows the target design. Cross-cloud active-active failover (GSLB) is not implemented in `deploy/`; each cloud has its own landing zone. The thresholds below are illustrative policy values. See [CLAIMS.md](CLAIMS.md).

## System Architecture Diagram

```mermaid
graph TD
    %% Global Styles for Enterprise Polish
    classDef predictive stroke:#f39c12,stroke-width:3px,stroke-dasharray: 5 5;
    classDef infra fill:#2c3e50,color:#fff,stroke:#34495e,stroke-width:2px;
    classDef healthcare fill:#e74c3c,color:#fff,stroke:#c0392b,stroke-width:2px;
    classDef storage fill:#7f8c8d,color:#fff,stroke:#333;

    subgraph Edge ["<b>Robotics Edge Layer (Clinical Environment)</b>"]
        A[/"Kinematic Sensors (IoT)"/] --- B("Agentic Safety Node")
    end

    subgraph Platform ["<b>AIOps Control Plane (Multi-Cloud)</b>"]
        B -->|gRPC / TLS 1.3| C{"Data Orchestrator"}
        
        subgraph AI_Engine ["Predictive Intelligence"]
            C --> D[["LSTM/TCN Ensemble Model"]]
            D --> E{"Predictive Risk Scoring"}
        end

        C -.-> F[("TSDB Telemetry Store")]
    end

    subgraph Response ["<b>Resilience Engine (SRE)</b>"]
        E -->|p > 0.85| G{{"GitOps (ArgoCD)"}}
        E -->|p > 0.60| H{{"Self-Healing Circuit"}}
        
        G --> I[<b>Active-Active Failover</b>]
        H --> I
    end

    subgraph Compliance ["<b>Governance & Audit</b>"]
        I --> J["HIPAA / HDS Immutable Logs"]
        J --> K["Executive SLM Dashboard"]
    end

    %% Apply Styles
    class D,E predictive;
    class B,A healthcare;
    class G,I,C,K infra;
    class F,J storage;

```

## Technical Breakdown

| Component | Technology Stack | Responsibility |
| --- | --- | --- |
| **Edge Layer** | [Robotics Module](../src/golden/robotics) | Real-time kinematic telemetry ingestion and local safety mediation. |
| **Predictive Engine** | [AI Brain (LSTM/TCN)](../src/golden/ai) | Time-series forecasting to identify "pre-failure" signatures in sensor data. |
| **Resilience Engine** | [SRE / GitOps](../deploy/gitops) | Automated re-provisioning and failover via [ArgoCD](../deploy/gitops) based on risk scores. |
| **Audit Plane** | [Compliance Docs](compliance) | Ensures every automated action is logged for HIPAA and HDS regulatory standards. |

---

### Pro-Tip for your Portfolio:

Notice that I added **Probability Thresholds** (e.g., `p > 0.85`) to the diagram lines. This subtle detail demonstrates to hiring managers that you understand **Decision Science** and how to tune AI for operational reliability.


---


## Source: docs/architecture/03-infrastructure-topology.md

# 03: Multi-Cloud Infrastructure Topology

## Executive Overview

This document outlines the target global footprint of the **Golden Platform**. The goal is to minimise downtime for clinical operations with a **Multi-Cloud Active-Active** strategy.

> **What is implemented today:** independent per-cloud landing zones in [`deploy/terraform/live`](../deploy/terraform) (AWS, Azure, GCP, OCI) and OpenShift assets. The global load balancer, cross-cluster mesh and private interconnects described below are **design targets** — there is no GSLB or cross-cloud replication code in the repository. See [CLAIMS.md](CLAIMS.md).

The target orchestration layer spans Amazon Web Services (AWS), Microsoft Azure, **Google Cloud Platform (GCP)**, and Oracle Cloud Infrastructure (OCI), managed via a unified [Terraform](../deploy/terraform) and GitOps workflow.

## Global Distribution Map

The target design distributes workloads across the following managed Kubernetes clusters so that a regional or provider outage can be survived (not yet validated by a drill):

| Cloud Provider | Managed Service | Primary Region | Role |
| --- | --- | --- | --- |
| **AWS** | [Elastic Kubernetes Service (EKS)](../deploy/terraform) | `us-east-1` | Primary Inference Plane |
| **Azure** | [Azure Kubernetes Service (AKS)](../deploy/terraform) | `eastus` | Disaster Recovery & Data Sync |
| **GCP** | [Google Kubernetes Engine (GKE)](../deploy/terraform) | `us-central1` | **AI/ML Model Training & Big Data Analytics** |
| **OCI** | [Oracle Container Engine (OKE)](../deploy/terraform) | `us-ashburn-1` | High-Performance Robotics Edge Aggregator |

## Networking & Interconnectivity

* **Global Traffic Management** *(design target)*: An Anycast-based Global Load Balancer (GLB) would route clinical telemetry to the nearest healthy cluster based on latency and health checks.
* **Service Mesh Architecture**: An Istio-based service mesh ([`deploy/helm/service-mesh`](../deploy/helm/service-mesh)) is intended to provide secure, cross-cluster communication with mTLS, ensuring sensitive healthcare data is encrypted in transit between clouds.
* **GCP Cloud Interconnect** *(design target)*: Would leverage Google’s dedicated backbone for high-speed synchronization of [robotics telemetry](../src/golden/robotics) datasets used in training the [LSTM/TCN models](../src/golden/ai).
* **Private Interconnects** *(design target)*: Where available, Equinix Fabric or provider-specific interconnects (e.g., AWS Direct Connect to Azure ExpressRoute) are leveraged to minimize latency.

## Infrastructure as Code (IaC) Standards

All infrastructure is declared using modular [Terraform](../deploy/terraform) code.

* **Module Reusability**: Standardized modules for VPC/VNet/VPC (GCP), IAM/RBAC, and K8s node groups ensure environmental parity.
* **State Management**: Remote state is stored in KMS-encrypted, versioned buckets with a lock table ([`modules/aws/backend`](../deploy/terraform/modules/aws/backend)) to prevent race conditions during high-frequency [GitOps](../deploy/gitops) deployments.

---

### Key Portfolio Enhancement

By adding **GCP (GKE)** specifically for **Model Training**, you demonstrate a sophisticated understanding of cloud specialization: using AWS/Azure for reliable web/inference and GCP for its superior data-processing capabilities.


---


## Source: docs/architecture/04-predictive-reliability-framework.md

# 04: Predictive Reliability Framework

## Executive Overview

The **Predictive Reliability Framework (PRF)** is the core intelligence of the platform. It transitions the infrastructure from a reactive state (incident response) to a proactive state (pre-emptive remediation). By processing high-fidelity [kinematic telemetry](../src/golden/robotics), the framework aims to identify "pre-failure" signatures that threshold-based monitoring misses.

> Numbers in this document are **targets / SLO objectives**, not measurements. Models are trained on synthetic data ([`src/golden/ai/datasets`](../src/golden/ai/datasets/README.md)). Measured values and how to reproduce them are in [CLAIMS.md](CLAIMS.md).

## The Multi-Cloud Dual-Model Approach

The platform utilizes a hybrid inference strategy across [AWS/Azure/GCP/OCI/](architecture/03-infrastructure-topology.md) to balance accuracy and performance:

1. **LSTM (Long Short-Term Memory)**: Used for long-range trend analysis of system health and resource consumption to identify gradual degradation.
2. **TCN (Temporal Convolutional Network)**: Optimized for detecting rapid, high-frequency anomalies in robotics sensor data where local context is critical for safety.
3. **GCP Vertex AI / TPU Integration** *(design option, not implemented)*: Compute-heavy training could be offloaded to **Google Cloud Platform**. Today training runs locally or in CI via `make train` (CUDA → MPS → CPU) and drift-triggered `golden model retrain`.

## Predictive Action Lifecycle

The framework operates on a **Risk Probability (P)** scale to trigger specific operational tiers:

| Risk Level | Threshold | Automated Action | Response Tier |
| --- | --- | --- | --- |
| **Low** | | Baseline Logging | Observability Only |
| **Medium** | | Dynamic Scaling | Infrastructure Warm-up |
| **High** | | Traffic Shadowing | Self-Healing Circuit |
| **Critical** | | **Automated Failover** | [GitOps Re-provisioning](../deploy/gitops) |

## Clinical Safety & Resilience

In healthcare environments, downtime is life-critical. This framework maps infrastructure reliability directly to **Clinical SLOs**. If the AI predicts a failure in the [robotics telemetry stream](../src/golden/robotics), the target behaviour is a fast handover to a redundant cloud region—such as shifting critical workloads from EKS to [GKE](architecture/03-infrastructure-topology.md)—to minimise interruption for surgical edge devices. Cross-cloud handover is not implemented and its timing has not been measured.

## Financial Safety & Resilience

In fintech environments, downtime means direct financial loss and regulatory exposure. This framework maps infrastructure reliability to **Financial SLOs** (target objectives; the SLO actually encoded in Prometheus today is 99.9% availability and p95 < 500 ms per API, [`slo_rules.yml`](../observability/prometheus/rules/slo_rules.yml)):

* **Transaction Processing SLO** *(target)*: 99.9% of payment transactions complete within 100 ms end-to-end.
* **Fraud Detection SLO** *(target)*: fraud scoring within 50 ms per transaction. Quality targets are set per client after calibration; on synthetic data the trained model measures precision 0.753 / recall 0.951 / FPR 1.8% (`golden model retrain --force`).
* **Settlement SLO** *(target)*: End-of-day settlement batches complete within the clearing window with no data loss.

If the AI predicts a failure in the [payment processing pipeline](/src/golden/ai/pipelines/detect_fraud.py), the platform triggers automated failover:

1. **Payment Gateway Failover**: Traffic is rerouted to a standby payment processor (simulated in `payment-gateway`; exercised by [`payment-gateway-failure.sh`](../ops/sre/chaos/payment-gateway-failure.sh)). Failover time is not yet measured.
2. **Transaction Queue Protection** *(design)*: In-flight transactions would be buffered in Kafka with idempotent producers to prevent duplicate charges or lost payments. The current transaction engine does not use Kafka.
3. **Fraud Model Promotion**: When drift is detected, a retrained challenger is registered only if it passes the quality gate; promotion and rollback go through the model registry (`golden model`), with shadow/canary rollout.

## Performance Metrics

* **Prediction Lead Time** *(target)*: >5 minutes before critical failure.
* **Precision/Recall** *(target)*: >92% for clinical safety-critical anomalies and >95% for fraud, to be validated on client data. Not met on synthetic data today (fraud precision 0.753).
* **False Positive Rate** *(target)*: <2% for infrastructure alerts; <0.1% for transaction fraud flags (measured 1.8% on synthetic data).
* **Transaction Integrity** *(target)*: no duplicate charges or lost transactions during failover events.
* **Regulatory Response Time** *(target)*: incident reports prepared within the PSD2 Article 96 reporting window (4 hours for the initial report).

---

### Strategy for your Portfolio

This document signals that you don't just "do AI"—you know how to make AI **useful** for an enterprise. Highlighting the **Probability Thresholds** and the specialized use of **GCP for training** shows you understand the decision science and cost-efficiency required at the $500k+ salary level.


---


## Source: docs/architecture/05-active-active-resilience.md

# 05: Active-Active Resilience Strategy

> **Status: design target, not implemented.** `deploy/` provides independent per-cloud landing zones (AWS, Azure, GCP, OCI) and OpenShift assets. There is no GSLB, cross-cloud data replication or automated cross-cloud failover in the repository, and no RTO/RPO has been measured. What exists today: per-cluster GitOps reconciliation, governed remediation (`golden orchestrate`) and chaos scripts including [`region-failover-test.sh`](../ops/sre/chaos/region-failover-test.sh). See [CLAIMS.md](CLAIMS.md).

## Executive Overview

This document details the **Active-Active Resilience Strategy** for the [Golden Platform](../README.md). Unlike traditional Active-Passive setups, this architecture would process traffic simultaneously across multiple cloud providers (AWS, Azure, OCI). The design goal is an RTO (Recovery Time Objective) close to zero and a near-zero RPO (Recovery Point Objective) for critical healthcare workloads; both are targets until measured in a drill.

## Global Traffic Orchestration

Traffic would be distributed by a Global Server Load Balancing (GSLB) layer that performs real-time health checks on the [multi-cloud infrastructure](architecture/03-infrastructure-topology.md).

* **Latency-Based Routing**: Clinical telemetry from [robotics edge nodes](../README.md) is routed to the lowest-latency cluster.
* **Failover Automation**: If the [predictive reliability framework](architecture/04-predictive-reliability-framework.md) identifies a high probability of failure (), the GSLB automatically drains traffic from the compromised region before an outage occurs.

## Data Synchronization & Consistency

To maintain a unified state across [EKS, AKS, and OKE](architecture/03-infrastructure-topology.md), the design calls for a multi-region data mesh:

1. **Eventual Consistency for Analytics**: Telemetry data is asynchronously replicated to regional [TSDBs (Time Series Databases)](architecture/02-data-flow-diagrams.md) for AI training.
2. **Synchronous Replication for State**: Critical clinical state and configuration are managed via a globally distributed database with strictly defined quorum requirements to prevent "Split-Brain" scenarios.

## Predictive Failover Workflow

The integration between the [AI Brain](../README.md) and the [GitOps Engine](../README.md) allows for "pre-emptive" resilience:

| Stage | Trigger | Action |
| --- | --- | --- |
| **Detection** | [TCN Model Anomaly](architecture/04-predictive-reliability-framework.md) | Flagging of high-risk resource in Region A. |
| **Preparation** | [GitOps Sync](../README.md) | Scaling up redundant capacity in Region B. |
| **Execution** | **GSLB Shift** *(not implemented)* | Transition of traffic to healthy clusters. |
| **Recovery** | [Self-Healing Script](../README.md) | Automated root-cause analysis and re-provisioning of Region A. |

## Compliance & Auditability

Every failover event, whether manual or automated by AI, is designed to be captured in the tamper-evident, hash-chained audit log ([`src/golden/security/audit.py`](../src/golden/security/audit.py)). This ensures that even during high-velocity resilience maneuvers, the platform maintains a full audit trail for regulatory bodies.


---


## Source: docs/assets/images/README.md

# Visual Architecture & Design Assets

This directory contains the high-level diagrams and visual artifacts that document the **Golden Platform**. These images are referenced throughout the repository documentation to illustrate complex workflows, from the GitOps pipeline to the AIOps self-healing loops.

## Asset Catalog

### 1. System Architecture
* **File:** `architecture-diagram.png`
* **Description:** A high-level overview of the entire platform ecosystem. It visualizes the relationship between the Multi-Cloud Infrastructure (Terraform), the Kubernetes Control Plane (GKE), the Observability Stack (Splunk/Prometheus), and the Application Layer (Express.js).
* **Key Concept:** Demonstrates the **"Hub-and-Spoke"** design where the AIOps Engine sits at the center of the observability pipeline.

### 2. The AIOps Loop
* **File:** `aiops-selfhealing-pipeline.png`
* **Description:** Illustrates the closed-loop automation process:
    1. **Detect:** Telemetry data flows into the AIOps engine.
    2. **Predict:** The LSTM model forecasts an anomaly.
    3. **Act:** The system triggers an auto-scaling event or circuit breaker.
* **Key Concept:** Visual proof of the transition from **Reactive** to **Predictive** reliability.

### 3. GitOps Workflow
* **File:** `gitops-workflow.png`
* **Description:** Detailed flow of the Continuous Delivery pipeline. Shows how code moves from a GitHub Pull Request -> CI Checks -> Container Registry -> Flux/ArgoCD Synchronization -> Production Cluster.
* **Key Concept:** Enforces the **"Code is Law"** philosophy, where no manual changes are allowed in production.

### 4. Observability & Tracing
* **File:** `opentelemetry-trace.png`
* **Description:** A sample visualization of a distributed trace captured by the OpenTelemetry Collector. It highlights how a single user request is tracked across multiple microservices, exposing latency bottlenecks and error roots.
* **Key Concept:** Demonstrates **Deep Observability** beyond simple metrics.

---

## Usage
These images are embedded in the root `README.md` and module-specific documentation using standard Markdown syntax:

```markdown
![System Architecture](./assets/images/architecture-diagram.png)
````

### Talking Point
> I keep a dedicated `assets` folder because I believe **Visual Communication** is a core SRE skill. When I'm explaining a complex incident to leadership or onboarding a new engineer, having a clear `architecture-diagram.png` or `gitops-workflow.png` is often more valuable than the code itself. It proves I understand the *system design*, not just the syntax.


---


## Source: docs/compliance/01-hipaa-compliance-mapping.md

# 01: HIPAA Compliance & Security Mapping

> **Mapping, not certification.** This document maps platform controls to the HIPAA Security Rule. The platform has not been audited or certified against it. Rows describe the target control design; only items that link to code or config in this repository are implemented here, and the rest are requirements for the deploying organisation. See [CLAIMS.md](CLAIMS.md).

## Executive Summary

This document provides a traceability matrix between the **Golden Platform** technical controls and the **HIPAA Security Rule** (45 CFR § 164.312). The platform is designed to handle Protected Health Information (PHI) within clinical robotics and telemetry streams by enforcing encryption, zero-trust networking, and automated auditability.

## Technical Safeguards Mapping

| HIPAA Standard | Platform Control Implementation | Evidence Location |
| --- | --- | --- |
| **Access Control** (164.312.a.1) | RBAC-enforced access to Kubernetes clusters and AI inference engines using OIDC providers. | [`/terraform/iam`](https://www.google.com/search?q=%5B../../deploy)) |
| **Audit Controls** (164.312.b) | Immutable logging of all [GitOps](../deploy/gitops) changes and AI-driven failover events in a centralized TSDB. | [`/docs/architecture/05`](https://www.google.com/search?q=%5B../architecture)) |
| **Integrity** (164.312.c.1) | Digital signing of [container images](../scripts) and checksum verification of robotics telemetry packets. | [`/robotics/safety`](https://www.google.com/search?q=%5B../../src/golden)) |
| **Transmission Security** (164.312.e.1) | Mandatory **mTLS 1.3** for all service-to-service communication via Istio Service Mesh across multi-cloud regions. | [`/docs/architecture/02`](https://www.google.com/search?q=%5B../architecture)) |

## AI-Driven Compliance Monitoring

Unlike traditional platforms, this system leverages the [Predictive Reliability Framework](architecture/04-predictive-reliability-framework.md) to detect security anomalies:

* **Predictive Anomaly Detection**: The [LSTM/TCN models](../src/golden/ai) monitor telemetry access patterns to identify potential unauthorized PHI exfiltration or "man-in-the-middle" attacks at the robotics edge.
* **Governed Remediation**: If a security threshold is breached, the remediation engine can propose isolating the compromised node or rotating keys via GitOps; execution is gated by the `ActionGovernor` (autonomy mode, approvals, kill switch).

## Data Residency & Sovereignty

To support international healthcare standards (including **HDS** for French data), the [Multi-Cloud Topology](architecture/03-infrastructure-topology.md) ensures that patient data remains within geographically defined boundaries (e.g., `us-east-1` for US patients, `eu-west-1` for EU patients) through Kubernetes taints and affinity rules.

---

### Strategy for your Portfolio

This document signals to a **CISO or CTO** that you understand the liability and regulatory overhead of healthcare tech. It moves the repository from a "coding project" towards a product that a covered entity could take through its own HIPAA risk analysis. It does not make the product HIPAA-compliant on its own.


---


## Source: docs/compliance/02-data-privacy-hds.md

# 02: Data Privacy & HDS Compliance (Hébergement de Données de Santé)

> **Mapping, not certification.** This document maps platform controls to the French HDS framework. The platform has not been audited or certified against it. Rows describe the target control design; only items that link to code or config in this repository are implemented here, and the rest are requirements for the deploying organisation. See [CLAIMS.md](CLAIMS.md).

## Executive Overview

This document outlines the privacy controls implemented to meet the **HDS (Hébergement de Données de Santé)** certification requirements for the [Golden Platform](https://github.com/Here2ServeU/nawex-platform). These standards ensure that personal health data stored or processed within our [multi-cloud infrastructure](architecture/03-infrastructure-topology.md) remains secure, private, and under the control of the patient/provider.

## HDS Technical Requirements Mapping

As per the French Public Health Code, HDS certification covers six hosting activities. The platform's design maps to them as follows (certification applies to the hosting provider, not to this template):

| Activity | Technical Implementation | Platform Evidence |
| --- | --- | --- |
| **PaaS / IaaS Security** | Provisioning of secure virtual infrastructure across [EKS, AKS, and GKE](architecture/03-infrastructure-topology.md). | [`/terraform`](https://www.google.com/search?q=%5B../../deploy)) |
| **Application Hosting** | Secure container orchestration with automated [GitOps](../deploy/gitops) deployment pipelines. | [`/gitops`](https://www.google.com/search?q=%5B../../deploy)) |
| **Backup & DR** | Multi-region continuity design ([Active-Active Resilience](architecture/05-active-active-resilience.md), not implemented); near-zero RPO is a target. | [`/docs/compliance/04`](https://www.google.com/search?q=%5B.)) |
| **Data Encryption** | Mandatory Encryption-at-Rest (AES-256) and Encryption-in-Transit (TLS 1.3) across all cloud providers. | [`/docs/architecture/02`](https://www.google.com/search?q=%5B../architecture)) |

## Data Residency & Sovereignty

To satisfy European GDPR and French HDS requirements, the platform enforces strict data residency rules:

* **Region Pinning**: Critical clinical telemetry is pinned to specific EU regions (e.g., `eu-west-3` for France) to ensure data never leaves the required legal jurisdiction.
* **Cross-Border Controls**: The [GCP Vertex AI training loop](architecture/04-predictive-reliability-framework.md) utilizes anonymized data sets to ensure no PHI/PII is exposed during model optimization.

## Privacy by Design in AIOps

Our [Predictive Reliability Framework](architecture/04-predictive-reliability-framework.md) includes built-in privacy safeguards:

* **Data Minimization**: Only essential kinematic telemetry required for safety inference is processed by the [AI Brain](../src/golden/ai).
* **Automated Anonymization**: All telemetry streams are scrubbed of identifiable metadata at the [Robotics Edge](../src/golden/robotics) before ingestion into the cloud control plane.

---

### Strategy for your Portfolio

Adding **HDS** to your documentation highlights your ability to navigate complex international regulations. This is a massive differentiator for leadership roles in global healthcare tech.


---


## Source: docs/compliance/03-audit-logging-policy.md

# 03: Audit Logging & Monitoring Policy

> **Mapping, not certification.** This document maps platform controls to the audit requirements of HIPAA, HDS, PCI DSS and SOX. The platform has not been audited or certified against it. Rows describe the target control design; only items that link to code or config in this repository are implemented here, and the rest are requirements for the deploying organisation. See [CLAIMS.md](CLAIMS.md).

## Executive Overview

This document defines the technical standards for capturing, protecting, and reviewing audit logs within the [Golden Platform](https://github.com/Here2ServeU/nawex-platform). Per [HIPAA §164.312(b)](compliance/01-hipaa-compliance-mapping.md), the platform implements hardware, software, and procedural mechanisms that record and examine activity in information systems that contain or use electronic protected health information (ePHI).

## Scope of Logging

The platform captures granular telemetry across the entire [multi-cloud stack](architecture/03-infrastructure-topology.md):

| Log Category | Source Component | Data Captured |
| --- | --- | --- |
| **System Access** | [IAM / RBAC](../deploy/terraform) | User ID, Timestamp, Source IP, Success/Failure status. |
| **AI Decisioning** | [Predictive Brain](../src/golden/ai) | Risk probability scores (), input telemetry features, and triggered actions. |
| **Infrastructure** | [GitOps (ArgoCD)](../deploy/gitops) | Commit SHA, Author, and diffs of all environmental changes. |
| **Clinical Safety** | [Robotics Edge](../src/golden/robotics) | Kinematic anomaly flags and agentic safety mediation events. |
| **Financial Transactions** | [Transaction Engine](/src/golden/ai/pipelines/detect_fraud.py) | Transaction IDs, amounts, fraud scores, payment gateway responses, settlement events. |
| **Regulatory Compliance** | [Compliance Engine](/docs/compliance) | PCI-DSS scope validation, SOX control testing, PSD2 SCA decisions, GLBA access audits. |

## Immutability & Protection

To prevent log tampering and satisfy [HDS standards](compliance/02-data-privacy-hds.md), the following protections are enforced:

* **Write-Once-Read-Many (WORM)** *(deployment requirement)*: Logs should be streamed to encrypted, object-locked buckets in [GCP and AWS](architecture/03-infrastructure-topology.md). Object-lock buckets for logs are not provisioned by `deploy/terraform` today.
* **Cryptographic Hashing**: Every audit entry carries the SHA-256 of its predecessor, so editing or deleting an entry breaks the chain ([`src/golden/security/audit.py`](../src/golden/security/audit.py); `golden security status` reports chain validity).
* **Separation of Duties**: The [SRE team](../ops/sre) cannot modify or delete logs; only the dedicated Security Auditor role has read-only access.

## Predictive Audit Review

Utilizing the [Predictive Reliability Framework](architecture/04-predictive-reliability-framework.md), the platform performs continuous, automated log analysis:

* **Anomaly Detection**: The [AI Brain](../src/golden/ai) flags unusual administrative patterns that may indicate credential compromise.
* **Automated Alerting**: High-risk security events raise Prometheus alerts and can trigger governed resource isolation. (Cross-cloud [active-active failover](architecture/05-active-active-resilience.md) is a design target.)

## Retention Requirements

Logs are retained according to the following schedule to meet legal mandates:

* **Active Logs**: 90 days in high-performance [TSDB](architecture/02-data-flow-diagrams.md).
* **Archive Logs**: 7 years in cold storage (GCS/S3) for HIPAA/HDS/SOX/GLBA regulatory look-backs.
* **Financial Transaction Logs**: 5 years minimum per PCI-DSS Requirement 10.7; 7 years for SOX-relevant systems.

---

### Strategy for your Portfolio

This policy proves you understand that **Observability is a Compliance Requirement**. By linking your [AI models](../src/golden/ai) to the auditing process, you demonstrate a "Security-First" engineering mindset.


---


## Source: docs/compliance/04-disaster-recovery-plan.md

# 04: Disaster Recovery (DR) Plan & Business Continuity

> **Status: plan with target objectives.** The RTO/RPO values below are targets, not measurements. Cross-cloud GSLB failover and multi-cloud data replication are not implemented in `deploy/` (each cloud is an independent landing zone). Replace targets with measured values by running the chaos scripts in [`ops/sre/chaos`](../ops/sre/chaos/README.md) on a real deployment. See [CLAIMS.md](CLAIMS.md).

## Executive Overview

This document defines the formal **Disaster Recovery (DR)** strategy for the [Golden Platform](https://github.com/Here2ServeU/nawex-platform). To satisfy **HIPAA Security Rule §164.308(a)(7)**, this plan describes how clinical robotics telemetry and AI inference services are intended to stay operational during catastrophic infrastructure failures through an [Active-Active Multi-Cloud](architecture/03-infrastructure-topology.md) architecture (design target).

## Recovery Objectives (RTO & RPO)

In a healthcare context, "Downtime = Clinical Risk." In a fintech context, "Downtime = Financial Loss and Regulatory Exposure." Our targets aim for fast recovery:

* **Recovery Time Objective (RTO)** *(target, unmeasured)*: **< 30 seconds** once a GSLB layer is in place to re-route traffic on regional failure. Not achievable with the current per-cloud deployment; until measured, quote it only as a target.
* **Recovery Point Objective (RPO)** *(target, unmeasured)*: **near-zero**, which requires the cross-cloud [data synchronisation](architecture/05-active-active-resilience.md) design to be built. No cross-cloud replication exists today.

### Fintech-Specific DR Requirements

* **Transaction Integrity** *(design)*: In-flight payment transactions would be preserved in Kafka with idempotent delivery during failover (the current transaction engine does not use Kafka).
* **Settlement Continuity** *(design)*: End-of-day settlement should resume from the last committed batch (the simulated gateway tracks batches via `/api/v1/settlement/batches`).
* **Regulatory Notification** *(process requirement)*: Initial notification to financial regulators within the PSD2 Article 96 window (4 hours) and per PCI DSS incident response requirements. Not automated in this repository.

## Multi-Cloud Failover Strategy

The platform avoids "Single Point of Failure" by distributing the [AI Brain](../src/golden/ai) and [Robotics Edge](../src/golden/robotics) logic across physically isolated providers:

1. **Primary Execution**: Distributed across [EKS (AWS)](../deploy/terraform) and [AKS (Azure)](../deploy/terraform).
2. **Immediate Failover Target** *(design)*: [GKE (GCP)](../deploy/terraform) and [OKE (OCI)](../deploy/terraform) would keep warm-standby capacity sized to absorb clinical traffic.
3. **Predictive Intervention**: The [Predictive Reliability Framework](architecture/04-predictive-reliability-framework.md) initiates failover **before** an outage occurs, based on risk scores.

## Automated DR Procedures

All recovery actions are orchestrated via [GitOps](../deploy/gitops) to eliminate human error during high-stress incidents:

* **Health Probes** *(design)*: Global Load Balancers would monitor [Istio Service Mesh](architecture/02-data-flow-diagrams.md) endpoints every 5 seconds.
* **Traffic Shedding**: Automatic isolation of the failing region to prevent "Cascading Failures".
* **Tamper-evident Audit Trail**: Every DR event is logged as a Git commit and as an entry in the hash-chained audit log (see the [HIPAA mapping](compliance/01-hipaa-compliance-mapping.md)).

## Testing & Validation

To ensure plan effectiveness, the [SRE team](../ops/sre) conducts:

* **Quarterly Chaos Drills** *(recommended cadence)*: Run [`region-failover-test.sh`](../ops/sre/chaos/region-failover-test.sh) and record measured recovery time; GSLB shifts can be verified once [GSLB](architecture/05-active-active-resilience.md) exists.
* **Continuous Compliance Checks**: Automated [Terraform](../deploy/terraform) scans to ensure redundancy modules are never accidentally disabled.

---

### Strategy for your $500k+ Portfolio

This DR plan is the "Legal Backbone" of your architecture. It shows an executive that recovery is planned, has explicit targets, and has a way to be tested — the honest version of "designed not to fail".


---


## Source: docs/compliance/05-quantum-safe-encryption.md

# 05: Post-Quantum Cryptography (PQC) Readiness Plan

> **Status: readiness plan, not an implemented feature.** The repository does not ship ML-KEM (Kyber),
> ML-DSA (Dilithium) or SLH-DSA code, PQC certificates or PQC-signed audit logs. Today the audit trail
> is SHA-256 hash-chained ([`src/golden/security/audit.py`](../src/golden/security/audit.py)) and model
> artifacts are checked against a SHA-256 manifest (`golden security manifest`). This page describes how a
> deploying organisation would migrate to PQC. See [CLAIMS.md](CLAIMS.md).

## Executive Overview

Large-scale quantum computers would break today's public-key algorithms (RSA, ECDH, ECDSA). Data with a long confidentiality life — patient records, financial records, audit evidence — is exposed to "harvest now, decrypt later" collection today. In August 2024 NIST published the first PQC standards:

| Standard | Algorithm | Use |
| --- | --- | --- |
| **FIPS 203** | ML-KEM (from CRYSTALS-Kyber) | Key encapsulation (TLS key exchange) |
| **FIPS 204** | ML-DSA (from CRYSTALS-Dilithium) | Digital signatures |
| **FIPS 205** | SLH-DSA (from SPHINCS+) | Hash-based signatures (conservative backup) |

Symmetric cryptography (AES-256-GCM) and SHA-256/384 are considered adequate with current key sizes; the migration work is on key exchange and signatures.

## Phase 1 — Cryptographic inventory

Build a crypto bill of materials before changing anything:

| Area in this repo | What to record |
| --- | --- |
| TLS at ingress and mesh ([`deploy/helm/service-mesh`](../deploy/helm/service-mesh), [`deploy/helm/kong-gateway`](../deploy/helm/kong-gateway)) | Protocol versions, key-exchange groups, certificate algorithms, issuing CA |
| Terraform state and secrets ([`deploy/terraform`](../deploy/terraform)) | KMS key specs (symmetric vs asymmetric), who holds asymmetric keys |
| Audit and model integrity ([`src/golden/security`](../src/golden/security)) | Hash algorithms; any signatures (none today) |
| CI/CD and images ([`.github/workflows`](../.github/workflows)) | Image/commit signing approach (if adopted), OIDC token algorithms |
| Cloud provider services | Provider PQC support per service (load balancers, KMS, managed TLS) |

Output: a register of every asymmetric algorithm in use, the data it protects, and that data's required confidentiality lifetime.

## Phase 2 — Prioritise

Rank by (data lifetime) × (exposure). In this platform the first candidates would be:

1. External TLS for PHI and payment APIs (harvest-now-decrypt-later risk).
2. Service-to-service mTLS in the mesh.
3. Long-lived signatures: audit-log anchors, model-artifact manifests, release signing.

## Phase 3 — Hybrid migration

* **Key exchange:** enable hybrid X25519 + ML-KEM-768 groups where the TLS stack and load balancers support them (several cloud load balancers and recent OpenSSL/BoringSSL builds do). Hybrid keeps classical security if an ML-KEM implementation flaw is found.
* **Signatures:** add ML-DSA alongside existing signatures for audit anchors and artifact manifests once the signing toolchain supports it; keep verifying both during transition.
* **Crypto agility:** keep algorithm choice in configuration, not code, so a second migration is a config change.

## Phase 4 — Validate and monitor

* Handshake success and latency before/after enabling hybrid groups (record p95 per endpoint).
* Interoperability tests with partners, payment processors and EHR systems.
* A recurring check that no new non-agile asymmetric crypto enters the inventory.

## Compliance Alignment

PQC is not yet a stated requirement of HIPAA, HDS, PCI DSS or SOX. This plan supports their long-term data-protection expectations and aligns with NIST's PQC guidance. See [HIPAA mapping](compliance/01-hipaa-compliance-mapping.md), [HDS](compliance/02-data-privacy-hds.md), [PCI DSS](compliance/06-pci-dss-compliance-mapping.md) and [SOX](compliance/07-sox-compliance-mapping.md).

### Fintech considerations

* **Transaction signing:** evaluate ML-DSA for long-lived non-repudiation records once HSM vendors support it.
* **Payment channels:** hybrid ML-KEM key exchange depends on processor and scheme support; track it in the inventory.
* **HSMs:** confirm the vendor's FIPS 203/204 roadmap before committing to timelines.


---


## Source: docs/guides/EXECUTIVE-PORTFOLIO.md

# Golden Platform: Predictive Safety & Resilience Platform

> Every number on this page is either reproducible with a command or labelled as a target. See [CLAIMS.md](CLAIMS.md).

## Executive Summary: Bridging the Gap Between AI and Infrastructure

The **Golden Platform** is an enterprise modernization template designed for high-availability **healthcare** and **fintech** environments. It combines **classical ML (LSTM/TCN forecasters, an explainable fraud model)** with per-cloud landing zones (AWS, Azure, GCP, OCI, OpenShift) and governed remediation, with the goal of moving operations from reactive to predictive for [robotics telemetry streams](../src/golden/robotics) and [financial transaction processing](../src/golden/services/fintech). The API availability **SLO objective is 99.9%** ([`slo_rules.yml`](../observability/prometheus/rules/slo_rules.yml)); there is no production deployment yet, so no measured uptime is claimed.

## Architectural Excellence (Golden Project Standard)

This project uses the Golden Project structure to support SOC 2, HIPAA, [PCI-DSS](compliance/06-pci-dss-compliance-mapping.md) and [SOX](compliance/07-sox-compliance-mapping.md) auditability. These are **control mappings, not certifications** — see [docs/compliance](compliance/01-hipaa-compliance-mapping.md).

* **[Core AI Brain](../src/golden/ai)**: LSTM for long-range trends and TCN for high-frequency anomalies (`make train`), plus a trained, gated fraud model. On synthetic data, `golden model retrain --force` reports precision 0.753, recall 0.951, AUC 0.994 for the fraud model. No precision figure is claimed for production data.
* **[Multi-Cloud Topology](architecture/03-infrastructure-topology.md)**: Per-cloud landing zones for **AWS, Azure, GCP and OCI** through modular [Terraform](../deploy/terraform) and [GitOps](../deploy/gitops). Each cloud is deployed independently; cross-cloud active-active routing (GSLB) is a design target, not implemented.
* **[Resilience Engine](architecture/05-active-active-resilience.md)**: [Predictive failover logic](architecture/04-predictive-reliability-framework.md) and governed remediation (`golden orchestrate`). Recovery time is **not yet measured**; capture it with the chaos scripts in [ops/sre/chaos](../ops/sre/chaos/README.md).

## Ph.D. Research Implementation

The platform is a reference implementation of AI research on healthcare resilience and fintech safety (synthetic data from [`src/golden/ai/datasets`](../src/golden/ai/datasets/README.md)):

* **Agentic Safety Mediation**: Kinematic telemetry analysis at the [Robotics Edge](../src/golden/robotics) to flag pre-failure signatures.
* **MLOps Lifecycle**: Experiment tracking, a gated model registry, PSI/KS drift-triggered retraining and canary/shadow rollout (`golden model`).
* **Fintech Fraud Detection**: Explainable 5-signal transaction scoring, payment gateway failover simulation and settlement batches. In-process scoring measured at p95 ≈ 2 ms on a laptop (no network; see [CLAIMS.md](CLAIMS.md)); end-to-end latency under load is not yet measured.
* **Financial Compliance Mappings**: PCI-DSS, SOX, PSD2/Open Banking and GLBA control mappings.

Quantum methods are **not implemented**; they are explored only in the research note [06-quantum-optimization-layer.md](architecture/06-quantum-optimization-layer.md).

## Compliance and Governance

The platform is designed to be mapped to **HIPAA**, **SOC 2**, **French HDS**, **PCI-DSS**, **SOX**, **PSD2** and **GLBA**. It is not certified or audited against any of them.

* **Tamper-evident audit trail**: SHA-256 hash-chained audit log with PHI/PII redaction ([`src/golden/security/audit.py`](../src/golden/security/audit.py)). Post-quantum signing is a [readiness plan](compliance/05-quantum-safe-encryption.md), not a feature.
* **[Disaster Recovery Plan](compliance/04-disaster-recovery-plan.md)**: Multi-region / multi-cloud continuity design with target RTO/RPO, to be validated by drills.
* **Financial Data Protection**: Tokenization-first design for cardholder data and segregation of duties for SOX (design; see the PCI mapping for what is implemented).


---


## Source: docs/guides/interview-demo.md

# Interview Demo Runbook

Use this runbook to showcase production-style reliability engineering in 10–15 minutes.

## Demo Flow (10–15 minutes)
1. **Show Architecture**: Highlight the multi-domain structure (AI, app, GitOps, Terraform, SRE).
2. **Start Services**: App + Orchestrator, then robotics demo (optional).
3. **Show Observability**: Live metrics and `/metrics` payload.
4. **Inject Chaos**: Latency, error spike, CPU, memory leak.
5. **Explain AIOps Loop**: Observe → Analyze → Plan → Execute.
6. **Show Remediation**: Reset with `/ops/heal` and demonstrate recovery.

## Tools to Showcase
- **Observability**: Prometheus metrics endpoint, log-driven AIOps.
- **Chaos Engineering**: Built-in chaos endpoints + traffic generator.
- **Security & Compliance**: SOC2/HIPAA docs in `docs/compliance/`.
- **GitOps**: ArgoCD/Flux manifests in `gitops/`.
- **Infrastructure-as-Code**: Terraform modules in `terraform/`.
- **Kubernetes Packaging**: Helm charts in `helm/`.
- **Load Testing**: k6 script in `tools/k6/`.
- **API Exercises**: VS Code REST client file in `tools/http/`.
- **Supply Chain Security**: Trivy script in `scripts/`.

## Suggested Talking Points
- “The app is designed to emit golden signals out-of-the-box.”
- “Chaos endpoints make reliability measurable, not theoretical.”
- “The AI loop automates detection and remediation safely in dry-run by default.”
- “Everything is documented and reproducible—GitOps + IaC + runbooks.”

## Fast Commands
```bash
scripts/tools/healthcheck.sh
scripts/tools/chaos_demo.sh
scripts/tools/heal.sh
```


---


## Source: docs/guides/quickstart.md

# Quickstart (Local Demo)

This guide brings up the Express app, the AIOps orchestrator, and the robotics demo for interview-ready demos.

## Prerequisites
- Node.js 18+
- Python 3.10+
- Docker + Docker Compose
- jq (for JSON formatting in scripts)

## 1) Bootstrap
```bash
make bootstrap
```

## One-Click Demo Launcher
```bash
make demo
```

To include robotics:
```bash
DEMO_ROBOTICS=1 bash make demo
```

## 2) Start the Express App (Terminal A)
```bash
make up
```

## 3) Start the AIOps Orchestrator (Terminal B)
```bash
golden orchestrate
```

## 4) (Optional) Start the Robotics Demo (Terminal C)
```bash
docker compose --profile robotics up -d
```

## 5) Validate
```bash
scripts/tools/healthcheck.sh
```

## 6) Trigger Chaos
```bash
scripts/tools/chaos_demo.sh
```

## 7) Heal / Reset
```bash
scripts/tools/heal.sh
```

## Notes
- The AI orchestrator reads config from `src/golden/ai/agents/agent_config.yaml`.
- To read real app metrics, set `source: http` in that config.


---


## Source: docs/guides/splunk-observability.md

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
* **ArgoCD:** Manages the lifecycle of the Splunk Forwarder configurations (`deploy/gitops/argocd/app-splunk-forwarder.yaml`).
* **Flux:** Ensures immutable configuration state across clusters (`deploy/gitops/flux/apps/resources/splunk-forwarder-helmrelease.yaml`).

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
cd deploy/terraform/live/aws/splunk
terraform apply -auto-approve
# Output: splunk_hec_endpoint, splunk_admin_token


---


## Source: docs/guides/troubleshooting.md

# Troubleshooting Guide (All Domains)

## 1) Application (Express App)
**Symptoms**: App won’t start, 5xx responses, /metrics empty
- Ensure dependencies are installed: `npm --prefix app install`
- Check port 8080 is free
- Verify `/metrics` is reachable: `scripts/tools/healthcheck.sh`

## 2) AIOps Orchestrator
**Symptoms**: Import errors, no cycles, config not loaded
- Verify `ai/.venv` exists and dependencies installed
- Ensure `src/golden/ai/__init__.py` exists (package imports)
- Check `src/golden/ai/agents/agent_config.yaml` for `source: http` and endpoint

## 3) Data Pipelines (src/golden/ai/pipelines)
**Symptoms**: Model training failures, missing data
- Confirm required Python libs are installed
- Run pipeline scripts from repo root to preserve paths

## 4) Remediation Engine
**Symptoms**: No actions executed, rules ignored
- Validate YAML syntax in `src/golden/ai/remediation/remediation_rules.yaml`
- Confirm `executor.mode` is `active` if you want live actions

## 5) Observability
**Symptoms**: Metrics missing, noisy signals
- Validate `/metrics` output
- Reduce chaos injection or reset state via `/ops/heal`

## 6) GitOps (ArgoCD/Flux)
**Symptoms**: Manifests not syncing
- Verify cluster context in kubeconfig
- Validate YAML schemas in `gitops/`

## 7) Helm Charts
**Symptoms**: Chart install fails
- Run `helm lint` on the relevant chart
- Check `values.yaml` required fields

## 8) Kubernetes Manifests
**Symptoms**: Pods crashloop, service unreachable
- Validate namespace and service selectors
- Check `k8s/` manifests for port alignment

## 9) Terraform
**Symptoms**: Plan/apply failures
- Verify provider credentials and region settings
- Run `terraform fmt` and `terraform validate`

## 10) Robotics Demo (docker-compose)
**Symptoms**: Containers fail to build/start
- Ensure Docker is running
- Check for file path issues in `src/golden/robotics/grpc/Dockerfile`

## 11) Scripts & Tooling
**Symptoms**: `jq` missing, scripts fail
- Install `jq` or remove `| jq .` in scripts
- Ensure scripts are executable: `chmod +x scripts/*.sh`


---


## Source: docs/robotics/README.md

# Robotics Demo (Clinical Telemetry Loop)

This module simulates a **robotics telemetry stream** and a **safety watchdog** to demonstrate how the platform ingests edge signals and validates resilience behavior in real time.

## What It Shows
* **High-frequency telemetry** from a simulated surgical robot
* **gRPC service** acting as the “brain” for ingest/processing
* **Safety watchdog** that verifies agent health and logs the results

## Components
* **surgical-brain**: gRPC server that ingests telemetry
* **surgical-robot**: gRPC client that emits telemetry
* **safety-watchdog**: health check runner for agents

## Run the Robotics Demo
```bash
docker compose --profile robotics up -d
```

## Run from One-Click Demo
```bash
DEMO_ROBOTICS=1 bash make demo
```

## Logs & Outputs
- Docker logs for each container
- Local log volume: `robotics/logs/`

## Talking Point
“This demo proves the AIOps pipeline can ingest **edge telemetry** in a healthcare setting and validate safety agent availability under load.”


---


## Source: deploy/gitops/README.md

# GitOps Control Plane

**Automated Configuration Management for the Express AI-Driven Platform**

This directory defines the GitOps control plane, utilizing **ArgoCD** and **Flux** to manage the lifecycle of the Web App Workload, Observability Stack, and Platform Infrastructure. It enforces a "Code is Law" philosophy, ensuring that the desired state defined in Git is always reflected in the cluster.

---

## Directory Layout

### 1. ArgoCD (Application Layer)
Located in `argocd/`. Manages high-level applications and ensuring continuous synchronization.

* `namespace.yaml`: Bootstraps the `argocd` namespace.
* `project-platform.yaml`: Defines the ArgoCD Project with restricted source/destination policies.
* `app-express-app.yaml`: Deploys the **Web App Workload** (Node.js/Express).
* `app-splunk-forwarder.yaml`: Deploys the Splunk Universal Forwarder DaemonSet.
* `app-monitoring-stack.yaml`: Deploys Prometheus and Grafana for metrics.
* `app-kafka-zookeeper.yaml`: Deploys the event streaming backbone.

### 2. Flux (Infrastructure Layer)
Located in `flux/`. Manages low-level cluster resources and automated reconciliation.

* `namespace.yaml`: Bootstraps the `flux-system` namespace.
* `gitrepository-platform.yaml`: Defines the source connection to this repository.
* `kustomization-platform.yaml`: The top-level entry point for infrastructure reconciliation.
* `apps/express-app-helmrelease.yaml`: HelmRelease definition for the Web App.
* `apps/resources/splunk-forwarder-helmrelease.yaml`: HelmRelease for Splunk logging.

### 3. Policies (Compliance & Security)
Located in `policies/`. Documentation on how this architecture satisfies regulatory controls.

* `drift-detection.md`: Explains the auto-sync and self-heal mechanisms.
* `soc2-gitops-controls.md`: Details how GitOps meets SOC 2 Type II requirements (Change Management, Audit Trails).

---

## Usage Guide: ArgoCD

To bootstrap the Application Layer using ArgoCD:

1. **Install ArgoCD** (if not already present):
    ```bash
    kubectl apply -n argocd -f [https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml](https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml)
    ```

2. **Apply Platform Manifests**:
    ```bash
    kubectl apply -f deploy/gitops/argocd/namespace.yaml
    kubectl apply -f deploy/gitops/argocd/project-platform.yaml
    ```

3. **Deploy Applications**:
    ```bash
    kubectl apply -f deploy/gitops/argocd/app-express-app.yaml
    kubectl apply -f deploy/gitops/argocd/app-splunk-forwarder.yaml
    ```

**Result:** ArgoCD will begin synchronizing the Web App and Splunk Forwarder immediately.

---

## Usage Guide: Flux

To bootstrap the Infrastructure Layer using Flux:

1. **Install Flux CLI & Controllers**:
    ```bash
    flux install --namespace flux-system
    ```

2. **Apply Source & Kustomization**:
    ```bash
    kubectl apply -f deploy/gitops/flux/namespace.yaml
    kubectl apply -f deploy/gitops/flux/gitrepository-platform.yaml
    kubectl apply -f deploy/gitops/flux/kustomization-platform.yaml
    ```

**Result:** Flux will enter a continuous reconciliation loop (1-minute interval), ensuring that any drift in the `helm/` charts is instantly corrected.


---


## Source: deploy/gitops/argocd/README.md

# ArgoCD Control Plane & Application Manifests

This directory contains the **ArgoCD Application** definitions. While the `helm/` directory contains the *blueprints* (templates), this directory contains the *instructions* that tell ArgoCD where to deploy those blueprints and with what parameters.

These manifests act as the binding layer between the Git repository and the Kubernetes cluster, enforcing the **"Code is Law"** philosophy of GitOps.

## Directory Structure

* **`app-splunk-forwarder.yaml`**: ArgoCD definition for the Splunk Universal Forwarder (Log Shipping).
* **`app-monitoring-stack.yaml`**: ArgoCD definition for the Prometheus & Grafana stack (Metrics & Dashboards).
* **`app-datadog.yaml`**: ArgoCD definition for the Datadog Agent (Unified Observability).
* **`app-dynatrace.yaml`**: ArgoCD definition for the Dynatrace Operator (Full-Stack Intelligence).

*(All manifests follow the standard "App of Apps" pattern, pointing to their respective charts in `helm/`.)*

## Core Capabilities & SRE Value

### 1. Automated Drift Detection & Self-Healing
* **Problem:** "Snowflake Clusters." Administrators making manual changes via `kubectl edit` that are lost during the next update.
* **Solution:** These manifests configure ArgoCD to monitor the cluster state every 3 minutes. If a manual change is detected, ArgoCD flags it as "Out of Sync."
* **Impact:** **Immutability.** If enabled, the `selfHeal` policy instantly reverts manual changes, ensuring the cluster always matches the Git repo.

### 2. The "App of Apps" Pattern
* **Problem:** Manually applying 50 different `.yaml` files to bootstrap a new cluster.
* **Solution:** We can create a parent "Root App" that points to this directory. ArgoCD will then recursively discover and deploy every application defined here.
* **Impact:** **One-Click Disaster Recovery.** We can spin up a brand new production cluster in a new region by applying a single manifest.

### 3. Progressive Delivery Control
* **Problem:** Deploying a broken config to all environments simultaneously.
* **Solution:** These manifests allow us to override `values.yaml` for specific environments (e.g., setting `replicaCount: 1` for Staging vs `replicaCount: 50` for Prod) without changing the underlying Helm chart.
* **Impact:** **Safe Rollouts.** We can test changes in Staging using the exact same artifacts that will go to Production.

## Usage Guide

**To Deploy a New Service:**
1. Create a new file in this directory (e.g., `app-my-service.yaml`).
2. Paste the standard ArgoCD Application boilerplate.
3. Point the `source.path` to your Helm chart (e.g., `deploy/helm/my-service`).
4. Commit to Git. ArgoCD will automatically pick it up and deploy it.

**Example Manifest (Splunk):**
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: splunk-forwarder
  namespace: argocd
spec:
  project: default
  source:
    repoURL: '[https://github.com/Here2ServeU/nawex-platform](https://github.com/Here2ServeU/nawex-platform)'
    targetRevision: HEAD
    path: deploy/helm/splunk-forwarder
  destination:
    server: '[https://kubernetes.default.svc](https://kubernetes.default.svc)'
    namespace: monitoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
````

### Talking Point

> I organize my `deploy/gitops/argocd` folder to separate the *definition* of the app from the *deployment* of the app. By keeping these manifests distinct from the Helm charts, I can manage multi-cluster deployments easily. For example, I can have an `app-prod.yaml` and `app-stage.yaml` that both point to the same chart but apply different sync policies or environment variables.


---


## Source: deploy/gitops/flux/README.md

# FluxCD Infrastructure Management

This directory contains the **FluxCD** configuration for the platform. While ArgoCD is used for application delivery (visualized in the "App of Apps" pattern), FluxCD is utilized here to demonstrate an alternative "headless" GitOps workflow, often preferred for bootstrapping the underlying cluster infrastructure itself.

## Directory Structure

* **`apps/resources/`**: Contains the `HelmRelease` definitions. These Custom Resources (CRs) instruct the Flux Helm Controller to install charts from the local `helm/` directory.
    * `splunk-forwarder-helmrelease.yaml`: Log shipping agent.
    * `monitoring-stack-helmrelease.yaml`: Prometheus & Grafana.
    * `datadog-helmrelease.yaml`: Datadog agent.

## Core Capabilities & SRE Value

### 1. Automated Drift Correction
* **Concept:** The Flux Controller polls this Git repository every 5 minutes.
* **Value:** If an administrator manually changes a Kubernetes deployment (e.g., changing a replica count via `kubectl`), Flux detects the drift and immediately reverts it to the state defined in Git. This enforces **Immutable Infrastructure**.

### 2. Source-Controller Architecture
* **Concept:** Unlike ArgoCD's "Push" model (where the server connects to the repo), Flux pulls artifacts into the cluster.
* **Value:** **Security Hardening.** The cluster does not need to expose any inbound ports or webhooks to the outside world. It reaches *out* to GitHub to fetch updates.

### 3. Helm Integration
* **Concept:** The `HelmRelease` object wraps the standard Helm chart.
* **Value:** We get the best of both worlds: the templating power of Helm (for defining the app) and the automation of Flux (for deploying the app).

## Usage Guide

**To Add a New Service:**
1. Create a standard Helm chart in the root `helm/` directory.
2. Add a new `.yaml` file in `apps/resources/` defining the `HelmRelease`.
3. Update `kustomization.yaml` to include the new file.
4. Commit to Git. Flux will pick up the change automatically.

### Interview Talking Point:
> You might notice I have both argocd and flux folders. I built it this way to demonstrate proficiency with both industry standards. In a real-world scenario, I often use Flux for the low-level cluster bootstrapping (CNI, CSI, Service Mesh) because it's lightweight and headless, and then I layer ArgoCD on top for the developer-facing applications so they get the nice UI.


---


## Source: deploy/gitops/policies/README.md

# GitOps Policy & Compliance Framework

This directory documents the **Governance Layer** of the platform. While the `argocd` and `flux` directories handle the *mechanics* of deployment, this directory defines the *rules* that ensure those deployments are secure, compliant, and auditable.

It serves as the bridge between **DevOps** (speed) and **SecOps/Audit** (control), proving that our automated workflows satisfy strict regulatory requirements like **SOC 2 Type II**.

## Directory Structure

* **`soc2-gitops-controls.md`**: A compliance mapping document. It details exactly how our GitOps workflow satisfies specific SOC 2 controls (e.g., *CC8.1 Change Management*).
    * **Key Insight:** "The Pull Request *is* the Change Request ticket. The Merge Approval *is* the CAB approval."
* **`drift-detection.md`**: The operational playbook for handling "Configuration Drift."
    * **Key Insight:** Defines the "Code is Law" policy—how we detect, alert on, and auto-remediate manual changes made directly to the cluster (Shadow IT).

## Core Capabilities & SRE Value

### 1. Compliance as Code
* **Problem:** "Audit Week" is a nightmare of screenshots and spreadsheet hunting.
* **Solution:** By moving all infrastructure changes into Git, we create an **Immutable Audit Trail**.
* **Impact:** **Continuous Compliance.** We don't "prepare" for audits; we are always audit-ready. The Git log provides the *Who, What, When, and Why* for every single production change.

### 2. The "Break-Glass" Protocol
* **Problem:** Strictly enforcing GitOps can hinder emergency response during a P0 outage.
* **Solution:** The `drift-detection.md` policy outlines our "Emergency Access" procedure. Engineers can manually patch the cluster to stop the bleeding, but the system will alert on the drift immediately, triggering a "Reconciliation Ticket" to backport the fix to Git.
* **Impact:** **Pragmatic Reliability.** We balance strict control with the need for speed during incidents.

### 3. Change Management Automation
* **Problem:** Developers waiting 3 days for a Change Advisory Board (CAB) meeting.
* **Solution:** We automate the CAB. If a PR passes all CI checks (Linting, Security Scan, Unit Tests), it is automatically approved for Staging.
* **Impact:** **Velocity.** We maintain high governance standards without slowing down the release lifecycle.

## Operational Standards

**Policy: Manual Changes**
> *Any manual change made via `kubectl` that is not backported to this repository within 24 hours will be automatically overwritten by the GitOps controller.*

**Policy: Secret Management**
> *No plain-text secrets are allowed in this repo. All secrets must be encrypted via Sealed Secrets or referenced via External Secrets Operator.*

### Interview Talking Point:

> I created this `policies` directory because I know that **SRE is about more than just uptime; it's about trust.** I use documents like `soc2-gitops-controls.md` to show auditors that our automated pipeline isn't a 'wild west'—it's actually *more* controlled than the old manual processes. I map every Git action to a compliance control, turning our GitHub repo into our primary evidence locker.


---


## Source: deploy/gitops/policies/drift-detection.md

# Drift Detection with ArgoCD & FluxCD

This platform uses **GitOps** to detect and remediate drift between:
- Desired state in Git
- Actual state in the cluster(s)

## ArgoCD

- Each `Application` in `deploy/gitops/argocd` has:

  ```yaml
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
  ```

- **What this gives you:**
  - If someone changes a resource directly via `kubectl`, ArgoCD detects the diff and:
    - Flags it as **OutOfSync**
    - Auto-syncs back to Git (self-heal)
  - Any manual hot-fixes must go through Git, producing a clear, auditable history.

## FluxCD

- The `Kustomization` in `deploy/gitops/flux/kustomization-platform.yaml` runs every minute:

  ```yaml
  interval: 1m
  prune: true
  wait: true
  ```

- **What this gives you:**
  - Flux periodically compares live state against the manifests in Git.
  - Any drift is reconciled back to the desired state.
  - `prune: true` removes resources that were deleted in Git, avoiding config sprawl.

## How to Demo Drift Detection in Interviews

1. Show your ArgoCD UI or Flux events.
2. Manually edit a Deployment (e.g., scale replicas via `kubectl`).
3. Wait for reconciliation:
   - ArgoCD will mark the app as OutOfSync, then auto-sync.
   - Flux will show events indicating it reapplied the desired config.
4. Highlight how:
   - You treat the UI/CLI as *read-only*
   - Git + reviews are the single source of truth.


---


## Source: deploy/gitops/policies/soc2-gitops-controls.md

# SOC 2 Compliant GitOps Controls

**Security, Compliance, and Auditability Framework**

This repository is strictly architected to support **SOC 2 Type II** and **ISO 27001** compliance. By utilizing GitOps as the single source of truth, we enforce a strict separation of duties and maintain an immutable audit trail for all infrastructure changes.

---

## 1. Change Management & Peer Review

All modifications to the production environment—whether infrastructure or application code—must follow a strict lifecycle:

* **Pull Request Requirement:** Direct pushes to the `main` branch are disabled. All changes must originate from a feature branch submitted via Pull Request (PR).
* **Mandatory Review:** A minimum of one peer review (Code Owner) is required before merging.
* **Traceability:** Every commit represents a signed, timestamped record containing:
    * **Author:** Who made the change.
    * **Context:** Why the change was made (linked to Jira/Ticket ID).
    * **Diff:** Exactly what lines of configuration were altered.

## 2. Least Privilege & Separation of Duties

We enforce a strict boundary between human operators and the production cluster.

* **No Direct Write Access:** Engineers do not have `kubectl write` or `admin` permissions in the production cluster.
* **Machine Automation:** Only the **ArgoCD** and **Flux** controllers possess the necessary Service Account permissions to apply changes.
* **Read-Only Repository:** The cluster controllers have read-only access to this Git repository, preventing tampering from the compromised cluster side.

## 3. Continuous Audit Logging

Compliance is not a snapshot; it is a continuous state maintained by the Git history.

* **Immutable History:** The Git log serves as the legal record of all changes. History cannot be rewritten on protected branches.
* **Reconciliation Logs:** ArgoCD and Flux provide a secondary audit log confirming that the cluster state successfully converged with the Git state.
* **Drift Remediation:** Any unauthorized manual change to the cluster is immediately detected and overwritten by the automated controllers, ensuring the "Code is Law" principle.

## 4. Disaster Recovery & Rollbacks

In the event of a failure, the GitOps workflow provides an instant, tested recovery mechanism.

* **Instant Rollback:** Reverting a PR in Git triggers the controllers to immediately restore the previous known-good state in the cluster.
* **Mean Time to Recovery (MTTR):** Rollback time is bounded mainly by the GitOps reconciliation interval (or an immediate manual sync). Not measured in this repository.

## 5. Auditor Evidence Strategy

When demonstrating compliance to external auditors, use the following artifacts:

1. **Change Log:** Export the Git commit history for the audit period.
2. **Access Review:** Show GitHub/GitLab permission settings to prove branch protection and PR requirements.
3. **Drift Proof:** Demonstrate the "Drift Detection" policy by manually modifying a resource and showing its automatic correction.


---


## Source: deploy/helm/README.md

# Helm Chart Repository & Service Catalog

This directory acts as the **Internal Service Catalog** for the platform. It contains the custom Helm charts used to deploy the core infrastructure and applications to Kubernetes (EKS, AKS, GKE, or OKE).

These charts are designed to be **immutable blueprints**, ensuring that every deployment—whether in Staging or Production—adheres to the same reliability, security, and observability standards.

---

### 1. The Observability Data Pipeline
*These charts form the backbone of the AIOps platform, handling the ingestion and transport of high-volume telemetry data.*

#### `otel-collector/`
* **Purpose:** Deploys the **OpenTelemetry Collector** as a DaemonSet/Sidecar.
* **Problem Solved:** **Vendor Lock-in.** Decouples the generation of traces/metrics from their destination.
* **Value:** Allows us to route the same telemetry stream to multiple backends (e.g., Splunk *and* Prometheus) without modifying application code.

#### `kafka-zookeeper/`
* **Purpose:** Deploys a high-availability **Kafka** cluster with Zookeeper coordination.
* **Problem Solved:** **Data Loss during Spikes.** Acts as a durable buffer for log and metric data before it is processed by the AIOps engine.
* **Value:** Ensures zero telemetry data loss even if the backend analysis tool is temporarily down or overwhelmed.

#### `splunk-forwarder/` & `splunk-hec/`
* **Purpose:** Deploys the Universal Forwarder and configures the HTTP Event Collector (HEC) tokens.
* **Problem Solved:** **Log Fragmentation.** Aggregates logs from all nodes and pods into a central secure pipeline.
* **Value:** Provides the raw data required for the `sre/aiops` pattern matching scripts to detect anomalies.

#### `monitoring-stack/`
* **Purpose:** Deploys the standard metrics suite (Prometheus, Grafana, Alertmanager).
* **Problem Solved:** **Blind Spots.** Provides out-of-the-box dashboards for Node, Pod, and Cluster health.
* **Value:** Gives immediate "Single Pane of Glass" visibility into infrastructure health.

---

### 2. High-Speed Data Transport & State
*These charts manage the high-speed data transport required for background tasks and asynchronous AI processing.*

#### `redis/`
* **Purpose:** Deploys an isolated **Redis** instance as a high-performance message broker.
* **Problem Solved:** **Synchronous Bottlenecks.** Prevents primary application APIs from slowing down by offloading intensive AI/ML remediation tasks to background workers.
* **Value:** Provides a low-latency transport layer for [Celery](https://github.com/celery/celery) task queues, enabling distributed and asynchronous AI-driven infrastructure remediation.

---

### 3. Traffic Management & Security
*These charts enforce "Zero Trust" networking and manage ingress traffic.*

#### `service-mesh/`
* **Purpose:** Deploys the Service Mesh control plane (e.g., Istio/Linkerd).
* **Problem Solved:** **Insecure Internal Traffic.** Automatically injects mTLS (mutual TLS) sidecars to encrypt all pod-to-pod communication.
* **Value:** Enforces security compliance (encryption in transit) and enables advanced traffic strategies like **Canary Deployments** and **Circuit Breaking**.

#### `kong-gateway/`
* **Purpose:** Deploys the Kong API Gateway as the Ingress Controller.
* **Problem Solved:** **API Governance.** Centralizes authentication, rate-limiting, and routing rules at the edge.
* **Value:** Protects backend microservices from DDoS attacks and abusive usage patterns while simplifying API management.

---

### 4. Application & Developer Experience
*These charts standardize how developers interact with the platform.*

#### `express-app/`
* **Purpose:** A "Golden Path" chart for deploying stateless Node.js microservices.
* **Problem Solved:** **Configuration Drift.** Developers don't write their own Kubernetes manifests; they simply provide a Docker image and environment variables.
* **Value:** Enforces SRE best practices (Health Checks, Resource Limits, PDBs) by default for every application deployed.

#### `backstage/`
* **Purpose:** Deploys the Spotify Backstage developer portal.
* **Problem Solved:** **Service Discovery.** Provides a centralized catalog where developers can see the health, ownership, and documentation of all running microservices.
* **Value:** Reduces onboarding time and operational toil by giving developers a self-service UI to manage their services.

---

### Usage Guide

These charts are designed to be deployed via **ArgoCD** (GitOps). Do not run `helm install` manually in production.

**To deploy a new instance:**
1. Update the `values.yaml` in the respective environment folder (e.g., `deploy/gitops/envs/prod`).
2. Commit the change to Git.
3. ArgoCD will automatically sync the state.


---


## Source: deploy/helm/backstage/README.md

# Backstage Internal Developer Portal (IDP)

This directory contains the Helm chart for deploying **Backstage**, the open-source Internal Developer Portal (IDP). This platform serves as the "Front Door" to the entire infrastructure, aggregating service catalogs, documentation, and tooling into a single pane of glass.

## Directory Structure

* **`Chart.yaml`**: Defines the chart metadata and dependencies (e.g., PostgreSQL).
* **`values.yaml`**: The configuration layer. Contains critical settings for:
    * **Authentication:** Integration with GitHub/Okta for SSO.
    * **PostgreSQL:** Database connection strings for persistent state.
    * **Catalog Processors:** Rules for discovering `catalog-info.yaml` files in repositories.
* **`templates/`**: The Kubernetes manifests generated by Helm.
    * `deployment.yaml`: The main Backstage application backend/frontend.
    * `configmap.yaml`: Injects the `app-config.yaml` runtime configuration.
    * `service.yaml`: Internal cluster networking.
    * `ingress.yaml`: Exposes the portal to developers via https.

## Core Capabilities & SRE Value

### 1. Service Catalog & Ownership
* **Problem:** "Who owns this microservice?" & "Where is the API documentation?"
* **Solution:** Backstage automatically ingests `catalog-info.yaml` files from all microservice repos.
* **Impact:** Provides a real-time inventory of all running software, its owners, and its lifecycle status (experimental, production, deprecated).

### 2. Software Templates ("Golden Paths")
* **Problem:** Developers creating "snowflake" microservices with bad configurations, no security scanning, and missing monitoring.
* **Solution:** We provide standardized Scaffolder Templates (Node.js, Go, Python) with baked-in CI/CD, Helm charts, and SRE best practices.
* **Impact:** Enforces **Governance by Design**. Developers get a working "Hello World" app in 5 minutes that is already compliant with security and reliability standards.

### 3. TechDocs (Docs-like-Code)
* **Problem:** Outdated Wikis and scattered Google Docs.
* **Solution:** Renders Markdown documentation directly from the code repositories alongside the service.
* **Impact:** Ensures documentation lives with the code and is updated as part of the PR process.

## Deployment Guide

This chart is deployed via **ArgoCD**.

**Prerequisites:**
* PostgreSQL database must be provisioned (or enabled via `postgresql.enabled: true` in `values.yaml` for testing).
* A GitHub Personal Access Token (PAT) or App ID must be injected via Kubernetes Secrets to allow Backstage to read repositories.

**To Upgrade:**
1. Modify `values.yaml` (e.g., to add a new plugin or update the image tag).
2. Commit changes to Git.
3. ArgoCD will sync the new configuration automatically.


---


## Source: deploy/helm/express-app/README.md

# Standardized Express Microservice Chart

This directory contains the **"Golden Path"** Helm chart for deploying Node.js/Express microservices. It abstracts away the complexity of Kubernetes manifests, allowing developers to deploy production-ready applications by simply configuring a `values.yaml` file.

## Directory Structure

* **`Chart.yaml`**: Defines the chart version and application version. Acts as the interface for Helm dependencies.
* **`values.yaml`**: The default configuration layer. Defines SRE standards for:
    * **Resource Limits:** CPU/Memory requests and limits to prevent noisy neighbors.
    * **Probes:** Liveness and Readiness probes to ensure zero-downtime deployments.
    * **Autoscaling:** HPA configuration (min/max replicas) based on CPU utilization.
* **`templates/`**: The dynamic Kubernetes manifests generated by the chart.
    * `deployment.yaml`: The main workload definition, including sidecar injections (e.g., for mTLS or OTel).
    * `service.yaml`: ClusterIP service definition for internal networking.
    * `hpa.yaml`: Horizontal Pod Autoscaler configuration.
    * `serviceaccount.yaml`: Workload identity for fine-grained IAM permissions.

## Core Capabilities & SRE Value

### 1. "Guardrails" Against Drift
* **Problem:** Developers copy-pasting old YAML files results in "snowflake" deployments with missing security contexts or health checks.
* **Solution:** This chart forces adherence to a strict schema. Developers *cannot* deploy without defining essential parameters.
* **Impact:** 100% compliance with **Production Readiness Standards** across the fleet.

### 2. Baked-in Reliability
* **Problem:** Applications crashing during high load because they lack resource constraints or autoscaling logic.
* **Solution:** SRE best practices (HPA, PodDisruptionBudgets, and graceful shutdown periods) are hardcoded into the templates.
* **Impact:** Ensures **High Availability (HA)** by default. A junior developer using this chart automatically deploys a resilient service.

### 3. Observable by Design
* **Problem:** New services launching without logs or metrics flowing to the central platform.
* **Solution:** The chart automatically injects the necessary annotations for **Prometheus scraping** and **OpenTelemetry** sidecars.
* **Impact:** Instant visibility. As soon as a service is deployed, it appears on the Grafana dashboards.

## Usage Guide

**To deploy a new microservice:**
1. Create a new `values.yaml` file for your service (e.g., `my-service-values.yaml`).
2. Override the image tag and specific environment variables.
3. Deploy via ArgoCD (preferred) or Helm:
   ```bash
   helm install my-service ./express-app -f my-service-values.yaml


---


## Source: deploy/helm/kafka-zookeeper/README.md

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


---


## Source: deploy/helm/kong-gateway/README.md

# Kong API Gateway & Ingress Controller

This directory contains the Helm chart for deploying **Kong**, the cloud-native API Gateway. Kong serves as the **Unified Ingress Layer** for the platform, managing all external traffic entering the Kubernetes cluster.

Unlike a simple load balancer, Kong is configured here to act as an **API Governance Enforcement Point**, offloading critical logic (authentication, rate limiting, logging) from the microservices themselves.

## Directory Structure

* **`Chart.yaml`**: Defines the chart version and declares the dependency on the official Kong chart.
* **`values.yaml`**: The configuration layer. Defines SRE standards for:
    * **Proxy Settings:** Configures the LoadBalancer service to accept HTTP/HTTPS traffic.
    * **Ingress Controller:** Enables the controller to watch for standard Kubernetes `Ingress` resources.
    * **Plugins:** Globally enables plugins like `prometheus` (for metrics) and `correlation-id` (for tracing).
* **`templates/`**: Custom Custom Resource Definitions (CRDs) and configs.
    * `kong-plugin-ratelimit.yaml`: Defines global rate-limiting policies (e.g., 100 req/min per IP).
    * `kong-consumer.yaml`: Manages credentials for specific API consumers (services or external partners).
    * `ingress-class.yaml`: Registers Kong as the default ingress class for the cluster.

## Core Capabilities & SRE Value

### 1. Centralized API Security (Zero Trust)
* **Problem:** "Spaghetti Auth." Every microservice implementing its own authentication logic leads to bugs and security holes.
* **Solution:** We offload authentication to the Gateway. Kong validates JWTs (JSON Web Tokens) or handles OAuth2 flows *before* the request ever reaches the backend service.
* **Impact:** **Hardened Security Posture.** If a request reaches the backend, we know it is already authenticated. The backend developers focus on business logic, not auth code.

### 2. Traffic Control & DDoS Protection
* **Problem:** A single abusive client or a buggy script taking down the entire platform by flooding APIs.
* **Solution:** We apply **Rate Limiting** policies as Code via `KongPlugin` resources.
* **Impact:** **System Stability.** We can cap traffic at the edge, ensuring that Tier-1 services remain available even during traffic spikes.

### 3. Observability at the Edge
* **Problem:** Losing visibility into request latency before it hits the application pod.
* **Solution:** The Kong Prometheus plugin emits "Golden Signals" (Latency, Traffic, Errors, Saturation) for every single route.
* **Impact:** **Full-Stack Visibility.** We can detect network issues or 504 Gateway Timeouts immediately, often before the application even registers an error.

## Usage Guide

**To Expose a Service via Kong:**
Developers do not need to edit this chart. They simply add an annotation to their service's Ingress resource:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-service
  annotations:
    kubernetes.io/ingress.class: kong
    [konghq.com/plugins](https://konghq.com/plugins): global-rate-limit, request-transformer
spec:
  rules:
    - host: api.myplatform.com
      http:
        paths:
          - path: /my-service
            pathType: ImplementationSpecific
            backend:
              service:
                name: my-service
                port:
                  number: 80
```


---


## Source: deploy/helm/monitoring-stack/README.md

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


---


## Source: deploy/helm/otel-collector/README.md

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


## Source: deploy/helm/redis/README.md

# AI Worker Isolated Helm Chart

This chart deploys an isolated Celery worker environment as part of the [Golden Platform](https://github.com/Here2ServeU/nawex-platform).

## Features
- **Namespace Isolation**: Deploys into a dedicated `ai-worker-isolated` namespace.
- **Physical Isolation**: Uses Node Affinity to target specific worker nodes.
- **Security**: Includes a Network Policy to restrict cross-package communication.

## Prerequisites
- Kubernetes 1.19+
- Helm 3+
- Redis broker provisioned via [Terraform Redis module](../deploy/terraform/modules/redis).

## Installation
To install the chart with the release name `my-worker`:
```bash
helm install my-worker ./helm/redis


---


## Source: deploy/helm/service-mesh/README.md

# Service Mesh & Zero Trust Networking

This directory contains the Helm chart for deploying the **Service Mesh** (e.g., Istio or Linkerd) control plane. This component acts as the transparent infrastructure layer that manages service-to-service communication, enforcing security, observability, and traffic rules without requiring changes to application code.

## Directory Structure

* **`Chart.yaml`**: Defines the chart metadata and dependencies.
* **`values.yaml`**: The configuration layer. Defines SRE standards for:
    * **mTLS Mode:** Enforces "Strict" mutual TLS to ensure no unencrypted traffic is allowed within the mesh.
    * **Proxy Resources:** Sets CPU/Memory limits for the sidecar proxies injected into every pod.
    * **Tracing:** Configures the mesh to send distributed trace spans to the OTel Collector.
* **`templates/`**:
    * `control-plane.yaml`: Deploys the mesh controller and identity service.
    * `peer-authentication.yaml`: Defines cluster-wide security policies (Zero Trust).
    * `sidecar-injector.yaml`: Configures the mutating webhook that automatically adds the proxy container to new pods.

## Core Capabilities & SRE Value

### 1. Zero Trust Security (mTLS)
* **Problem:** "Soft Internal Network." Once an attacker is inside the cluster, they can sniff traffic between services (e.g., frontend talking to the database).
* **Solution:** The mesh automatically encrypts all traffic between pods using **Mutual TLS (mTLS)**. It also manages certificate rotation automatically.
* **Impact:** **Compliance & Security.** We satisfy PCI-DSS and HIPAA encryption requirements without developers having to implement HTTPS in every single microservice.

### 2. Progressive Delivery (Canary Deployments)
* **Problem:** "Big Bang" deployments. Releasing a new version to 100% of users immediately carries a high risk of outage.
* **Solution:** The mesh enables **Traffic Splitting**. We can route 1% of traffic to `v2` and 99% to `v1`. If `v2` is healthy, we slowly increase the percentage.
* **Impact:** **Risk Mitigation.** We can test new code in production with real traffic while limiting the blast radius of any bugs.

### 3. Golden Signals without Instrumentation
* **Problem:** Legacy apps or third-party containers that don't emit metrics.
* **Solution:** The sidecar proxy sits in front of the app and measures every request. It generates Request Rate, Error Rate, and Latency metrics automatically.
* **Impact:** **Instant Observability.** We get uniform dashboards for every service in the cluster, even the ones we didn't write.

## Usage Guide

**To Deploy:**
This chart is deployed via ArgoCD.

**To Inject the Mesh:**
Developers simply add an annotation to their Deployment or Namespace:

```yaml
metadata:
  annotations:
    sidecar.istio.io/inject: "true"
````

**To Configure a Canary Split:**
Apply a `VirtualService` or `TrafficSplit` resource:

```yaml
spec:
  hosts:
  - my-service
  http:
  - route:
    - destination:
        host: my-service
        subset: v1
      weight: 90
    - destination:
        host: my-service
        subset: v2
      weight: 10
```

### Talking Point:
> I introduced a **Service Mesh** to solve the 'Encryption at Rest vs. Encryption in Transit' problem. Managing SSL certificates for 50 microservices is a nightmare, so I offloaded it to the mesh. Now, we have **Strict mTLS** everywhere by default. It also gave us 'Red/Black' deployment capabilities for free—we can shift traffic percentages with a few lines of YAML, which is how we maintain 99.99% availability during deployments.


---


## Source: deploy/helm/splunk-forwarder/README.md

# Splunk Universal Forwarder & Log Aggregation

This directory contains the Helm chart for deploying the **Splunk Universal Forwarder**. This component acts as the "Log Shipper" for the Kubernetes cluster, automatically collecting logs from every node and container and forwarding them to the central Splunk Indexer.

It is designed to be lightweight and non-intrusive, ensuring that high-volume logging does not degrade the performance of the actual applications.

## Directory Structure

* **`Chart.yaml`**: Defines the chart version and metadata.
* **`values.yaml`**: The critical configuration layer. Defines SRE standards for:
    * **HEC Token:** The HTTP Event Collector token used for authentication with the Splunk backend.
    * **Index Management:** Defines which Splunk indices receiving data (e.g., `main` for apps, `audit` for security).
    * **Resource Limits:** Strict CPU/Memory caps to ensure the logging agent acts as a "good citizen" on the node.
* **`templates/`**:
    * `daemonset.yaml`: Deploys the forwarder on **every node** in the cluster to capture stdout/stderr from all pods.
    * `configmap.yaml`: Maps internal container log paths (e.g., `/var/log/containers/*.log`) to Splunk inputs.
    * `secret.yaml`: Securely mounts the HEC token so it is not exposed in plain text.

## Core Capabilities & SRE Value

### 1. Centralized Log Management
* **Problem:** "Ephemeral Logs." When a pod crashes and is replaced by Kubernetes, its local logs are deleted forever.
* **Solution:** The Forwarder streams logs in real-time to persistent storage (Splunk Cloud/Enterprise).
* **Impact:** **Forensic Reliability.** We can debug a crash that happened 3 days ago, even if the server that hosted the pod no longer exists.

### 2. Security & Compliance (Audit Trails)
* **Problem:** Meeting SOC 2 / HIPAA requirements for log retention and access control.
* **Solution:** We segregate logs into different indices (e.g., `PCI-Sensitive` vs `General-App`) via the `values.yaml` configuration.
* **Impact:** **Audit Readiness.** Security teams have a tamper-proof record of all system access, completely decoupled from the engineering team's operational logs.

### 3. "Unknown Unknowns" Analysis
* **Problem:** Prometheus metrics are pre-aggregated (you have to know what to measure). They can't tell you the specific error message caused by a rare edge case.
* **Solution:** Splunk captures the raw, high-cardinality text data.
* **Impact:** **Deep-Dive Root Cause Analysis.** Enables using Splunk Query Language (SPL) to search for specific error codes (e.g., `User ID: 5492 failed transaction`) that metrics would miss.

## Usage Guide

**To Deploy:**
This chart typically requires an existing Splunk HEC endpoint.

```bash
helm upgrade --install splunk-fwd ./splunk-forwarder \
  --set splunk.hecToken=$SPLUNK_HEC_TOKEN \
  --set splunk.hecUrl=[https://inputs.splunk-cloud.com:8088](https://inputs.splunk-cloud.com:8088) \
  -n monitoring
````

**Configuration Note:**
The `inputs.conf` generated by this chart automatically parses JSON logs, making them immediately searchable without complex extraction rules.

### Talking Point:
> I use the **Splunk Universal Forwarder** as a DaemonSet to solve the 'Ephemeral Container' problem. In Kubernetes, if a pod dies, the logs die with it. By shipping them immediately to Splunk, I ensure we have 100% forensic data retention. I also prefer the Forwarder over sidecars for every pod because it's much more resource-efficient—one agent per node handles all the traffic.


---


## Source: deploy/helm/splunk-hec/README.md

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


## Source: deploy/k8s/README.md

# Raw Kubernetes Manifests

This directory contains the **declarative YAML primitives** for deploying the application. While our production pipeline utilizes **Helm** charts (for templating) and **ArgoCD** (for GitOps), these files serve as the reference implementation for the underlying resources.

They demonstrate a clear understanding of core Kubernetes objects without the complexity of abstraction layers.

## Directory Structure

* **`namespace.yaml`**
    * Defines the logical isolation boundary (`aiops-demo`) for the workload.
    * **Why:** Prevents resource collisions and enables granular RBAC/Quota management.

* **`deployment.yaml`**
    * The primary workload definition.
    * **Key Features:** Defines the `ReplicaSet`, container image, resource requests/limits, and the `RollingUpdate` strategy to ensure zero-downtime deployments.

* **`service.yaml`**
    * Abstraction layer for pod discovery.
    * **Type:** `ClusterIP` (Internal only).
    * **Why:** Provides a stable virtual IP (VIP) and DNS name for the pods, regardless of their lifecycle.

* **`ingress.yaml`**
    * The external entry point.
    * **Function:** Routes external HTTP/HTTPS traffic to the internal `service`.
    * **Controller:** Configured for the standard Ingress Controller (e.g., Nginx or GCE).

## Usage Guide (Manual)

These files are typically used for local development (Minikube/Kind) or debugging.

**1. Create the Namespace:**
```bash
kubectl apply -f namespace.yaml
````

**2. Deploy the Stack:**

```bash
kubectl apply -f . -n aiops-demo
```

**3. Verify:**

```bash
kubectl get all -n aiops-demo
```

-----

### SRE Context: "Why Raw YAML?"

While Helm is superior for packaging, raw manifests are critical for **debugging**. When a Helm install fails, I inspect the rendered YAML against these primitives to identify if the issue lies in the template logic or the Kubernetes object definition itself.

```


---


## Source: ops/README.md

# /ops — SRE & Platform Governance for Golden Platform

This directory contains the central source of truth for **Site Reliability Engineering (SRE)** practices, **operational documentation**, and **platform governance** used to support the **Golden Platform Microservices** and the **Backstage Internal Developer Platform (IDP)**. All procedures adhere to a GitOps-first, audit-ready framework.

## Key Operational Areas

* **Checklists (`checklists/`):** Standardized checklists for pre/post-deployment validation and **SOC 2** compliance auditing.
* **Disaster Recovery (`dr/`):** Multi-cloud **DR Runbooks** focusing on failover for core services and **PostgreSQL** persistence.
* **On-Call (`on-call/`):** Policies and escalation paths refined for platform-specific severity levels and response times.
* **Playbooks (`playbooks/`):** Tactical guides for complex procedures like DB failover, Kafka draining, and **GitOps rollback**.
* **RBAC (`rbac/`):** **Kubernetes RBAC** templates defining least-privilege access for SREs, developers, and observers.
* **Scripts (`scripts/`):** Utility automation scripts for maintenance and monitoring tasks.
* **SRE (`sre/`):** General SRE principles, SLO/SLI definitions, and team structure documentation.
* **Terraform (`terraform/`):** Infrastructure-as-Code definitions for platform components (e.g., EKS/AKS/GKE clusters).


---


## Source: ops/checklists/README.md

# Operational Checklists for Golden Platform

Operational checklists are a critical component of our DevOps strategy, ensuring **consistency**, **auditability**, and **risk reduction** across all deployment and maintenance activities for the Golden Platform. They formalize the process of managing the Internal Developer Platform (IDP) and associated microservices.

## Available Checklists

| Checklist File | Purpose | Key Focus |
| :--- | :--- | :--- |
| [pre_deployment.md](../ops/runbooks/checklists/pre_deployment.md) | Standardize all steps required before a new release or update is initiated. | Pre-flight health checks, dependency verification, security scanning. |
| [post_deployment.md](../ops/runbooks/checklists/post_deployment.md) | Verify the health, connectivity, and functionality of all services immediately after a release. | Smoke testing, service mesh registration, alerting confirmation. |
| [soc2_controls_checklist.md](../ops/runbooks/checklists/soc2_controls_checklist.md) | Document and audit the continuous adherence to SOC 2 compliance requirements. | Access control, change management, system monitoring. |

## Usage

These documents should be utilized by all DevOps and SRE personnel prior to and following any changes to the production environment. They serve as a single source of truth for critical operational procedures.


---


## Source: ops/checklists/post_deployment.md

# Post-Deployment Checklist for Golden Platform

- [ ] **GitOps Status:** Deployment completed successfully via ArgoCD/Flux and reconciliation is healthy.
- [ ] **Infrastructure:** All sub-chart dependencies (e.g., PostgreSQL) are stable and healthy.
- [ ] **App Config:** New ConfigMap (app-config.yaml) successfully mounted and accessible by Backstage container.
- [ ] **Ingress/Connectivity:** Application is accessible via Ingress (`backstage.nrp-platform.com`) and TLS certificate is valid.
- [ ] **Health Probes:** Backstage Deployment Liveness and Readiness probes are passing consistently.
- [ ] **Backstage Catalog:** Catalog Processor successfully ingested all entities and no errors are present on the Catalog page.
- [ ] **SLOs/Telemetry:** No immediate increase in error rate or latency beyond defined SLO thresholds.
- [ ] **Monitoring:** Logs and traces confirm normal service behavior; synthetic checks are passing.
- [ ] **Alerting:** No abnormal alerts or warnings in the first 30–60 minutes.
- [ ] **Documentation:** Observability dashboards and runbooks are updated (if needed).
- [ ] **Handover:** Relevant ticket/issue is updated with deployment outcome and metrics summary.


---


## Source: ops/checklists/pre_deployment.md

# Pre-Deployment Checklist for Golden Platform

- [ ] **Change Approval:** Change request / ticket approved by required stakeholders.
- [ ] **Code Readiness:** Code merged to main branch and meets code standards.
- [ ] **CI Pipeline:** CI pipeline green (all unit/integration tests, linting, security scans passed).
- [ ] **Image Security:** Image scanned (Trivy/Snyk) and pushed to container registry; no critical vulnerabilities found.
- [ ] **Helm Integrity:** Helm chart version bumped and committed; `helm lint` and `helm template --dry-run` are successful.
- [ ] **Config Validation:** New configuration in `values.yaml` reviewed and validated against environment-specific secrets.
- [ ] **Infrastructure Capacity:** Kubernetes cluster quota and node capacity verified (resource limits available).
- [ ] **Secret Management:** New/rotated secrets (e.g., PostgreSQL credentials) verified in Secret Manager.
- [ ] **SLO Impact:** SLO impact reviewed; error budget available for potential deployment issues.
- [ ] **Runbooks:** Runbooks updated if new failure modes or service dependencies were introduced.
- [ ] **Rollback Plan:** Rollback plan clearly documented and tested (revert to previous stable tag).


---


## Source: ops/checklists/soc2_controls_checklist.md

# SOC 2 Controls Checklist (Deployment Focus)

- [ ] **Change Management:** All changes traceable to an approved ticket or work item.
- [ ] **Code Review:** At least one peer review before merge, ensuring security and adherence to standards.
- [ ] **Version Control:** Git history preserved (no force pushes to main/production branches).
- [ ] **Configuration:** All application/infrastructure configuration (e.g., Helm values) stored in Git.
- [ ] **Secrets Management:** Secrets are stored securely (Vault, AWS Secrets Manager, etc.) and NOT in Git.
- [ ] **CI Pipeline Checks:** CI pipeline includes:
    - [ ] Static code analysis
    - [ ] Dependency vulnerability scan
    - [ ] Container image scan
- [ ] **Deployment Tooling:** GitOps tool logs (ArgoCD/Flux) retained for the required audit period.
- [ ] **Production Access:** Access to production cluster restricted to GitOps service accounts + break-glass process.
- [ ] **DB Access Control:** Direct access to production database (PostgreSQL) is restricted and auditable.
- [ ] **Monitoring & Alerting:** Comprehensive monitoring and alerting is configured for all critical services.


---


## Source: ops/dr/README.md

# Disaster Recovery Runbooks for Golden Platform

Disaster Recovery (DR) strategies are essential for maintaining the **availability** and **integrity** of the Golden Platform microservices and the underlying Internal Developer Platform (IDP) (Backstage). This folder contains cloud-specific runbooks detailing the procedures required to restore service following a catastrophic event.

Our DR approach is focused on protecting the **stateful data** (primarily PostgreSQL) and quickly re-establishing service connectivity through GitOps pipelines.

## Scope

This directory contains cloud-specific DR runbooks for major providers:

* [aws_dr_runbook.md](../ops/runbooks/dr/aws_dr_runbook.md)
* [azure_dr_runbook.md](../ops/runbooks/dr/azure_dr_runbook.md)
* [gcp_dr_runbook.md](../ops/runbooks/dr/gcp_dr_runbook.md)
* [oci_dr_runbook.md](../ops/runbooks/dr/oci_dr_runbook.md)

## Runbook Outline

Each cloud-specific runbook outlines the following critical areas tailored to the Golden Platform environment:

1. **RPO / RTO Targets:** Defines acceptable data loss and service restoration time for microservices and IDP.
2. **Backup Strategy:** Details the mechanism for backing up critical data, particularly the Backstage PostgreSQL instance.
3. **Restore & Failover:** Step-by-step procedures for restoring stateful data and executing service failover to the DR region.
4. **Validation & Cutback:** Procedures for validating service functionality post-restore and returning traffic to the primary region.


---


## Source: ops/dr/aws_dr_runbook.md

# AWS Disaster Recovery Runbook for Golden Platform

## Scope
Covers critical components of the Golden Platform microservices platform:
* EKS clusters (for all microservices and Backstage IDP)
* **Backstage PostgreSQL RDS** / DynamoDB
* S3 buckets (for state and assets)
* ECR registries

## RPO / RTO
* RPO (target, not yet tested): 15 minutes (via automated backups and cross-region replication).
* RTO (target, not yet tested): 1–2 hours for full region failover of all microservices.

## Key Mechanisms
* Infrastructure as Code: EKS cluster and supporting services defined via **Terraform** (multi-region capable).
* Database: **Backstage PostgreSQL** configured with cross-region read replicas and automated backups.
* Storage: S3 versioning + cross-region replication for state and assets.
* Image Management: ECR image replication to secondary region.
* Deployment: Application deployment managed via **GitOps** (ArgoCD/Flux).

## Steps (Region Failover)
1. **Declare Disaster**
    * Confirm region-wide impact (not a localized issue).
    * Activate communications plan.
2. **Promote Backstage Database**
    * Promote the cross-region PostgreSQL replica (for Backstage) to primary.
    * Update connection secrets/credentials in AWS Secrets Manager (if needed).
3. **Provision Infra in DR Region**
    * Run Terraform against DR workspace/vars to create: EKS cluster, Networking, Load balancers, Supporting services.
4. **Restore State**
    * Restore any missing S3 state or configurations if required.
5. **Deploy Applications via GitOps**
    * Point ArgoCD/Flux to the new EKS cluster/context.
    * **Reconcile all applications from Git**, ensuring the Backstage chart and microservices deploy successfully.
6. **Validate & Cutover**
    * Execute smoke tests, SLO checks, and Post-Deployment Checklist.
    * Switch DNS (Route 53) to the DR load balancer endpoints.
7. **Post-Event**
    * Document incident and DR effectiveness.
    * Plan failback when the primary region is healthy.


---


## Source: ops/dr/azure_dr_runbook.md

# Azure Disaster Recovery Runbook for Golden Platform

## Scope
Covers critical components of the Golden Platform microservices platform:
* AKS clusters (for all microservices and Backstage IDP)
* **Azure PostgreSQL** / Azure SQL / Cosmos DB
* Azure Storage (for state and assets)
* Container Registry (ACR)

## RPO / RTO
* RPO (target, not yet tested): 15 minutes (via automated backups and cross-region replication).
* RTO (target, not yet tested): 1–2 hours for full region failover of all microservices.

## DR Strategy
* Infrastructure as Code: AKS cluster and supporting services defined via **Terraform** or Bicep (multi-region capable).
* Database: **Backstage PostgreSQL** configured with active geo-replication or cross-region backups.
* Storage: Geo-redundant storage (GRS) for state and assets.
* Image Management: ACR geo-replication to secondary region.
* Deployment: Application deployment managed via **GitOps** (ArgoCD/Flux).

## Steps (Region Failover)
1. **Assess Impact**
    * Verify that primary region is unavailable / severely degraded.
    * Activate communications plan.
2. **Failover Backstage Database**
    * Promote the geo-replicated database replica (for Backstage) to primary.
    * Update connection secrets/credentials in Azure Key Vault (if needed).
3. **Deploy AKS in DR Region**
    * Apply Terraform/Bicep with DR-specific variables to deploy the new AKS cluster, networking, and ingress.
4. **Restore State**
    * Restore any missing Azure Storage state or configurations if required.
5. **Re-point GitOps & Deploy Applications**
    * Configure ArgoCD/Flux to target DR AKS cluster.
    * **Reconcile all applications from Git**, ensuring the Backstage chart and microservices deploy successfully.
6. **Switch Traffic & Validation**
    * Update Azure Front Door / Traffic Manager / DNS to target DR endpoints.
    * Execute synthetic checks, SLO checks, and Post-Deployment Checklist.
7. **Post-Event**
    * Document incident and DR effectiveness.
    * Plan failback when the primary region is healthy.


---


## Source: ops/dr/gcp_dr_runbook.md

# GCP Disaster Recovery Runbook for Golden Platform

## Scope
Covers critical components of the Golden Platform microservices platform:
* **GKE clusters** (for all microservices and **Backstage IDP**)
* **Cloud SQL** (for Backstage PostgreSQL persistence) / Firestore
* **GCS buckets** (for state and assets)
* **Artifact Registry** (for container images)

## RPO / RTO
* RPO (target, not yet tested): 15 minutes (via automated backups and cross-region replication).
* RTO (target, not yet tested): 1–2 hours for full region failover of all microservices and the IDP.

## Strategy
* Infrastructure as Code: GKE clusters and networking managed via **Terraform** (multi-region capable).
* Database: **Cloud SQL for PostgreSQL** configured with cross-region replicas for minimal data loss.
* Storage: Multi-region or dual-region GCS for critical data and persistent volumes.
* Deployment: Application restoration managed entirely via **GitOps** (ArgoCD/Flux).

## Steps (Region Failover)
1. **Confirm Outage**
    * Validate issue is regional and not local.
    * Activate incident communications plan.
2. **Promote Backstage Database**
    * Promote the cross-region Cloud SQL PostgreSQL replica to primary.
    * Update connection secrets/credentials in Secret Manager (if needed).
3. **Create/Scale GKE in DR Region**
    * Apply Terraform DR workspace configs to provision the GKE cluster, Load Balancers, and necessary networking.
4. **Reconcile via GitOps**
    * Point GitOps controllers (ArgoCD/Flux) at DR GKE cluster context.
    * **Deploy all apps and platform services from Git**, ensuring the Backstage chart starts successfully.
5. **Switch Traffic**
    * Update **Cloud DNS** / load balancers to target the DR Ingress/Endpoints.
    * Confirm traffic flows correctly and smoke tests pass.
6. **Post-Event**
    * Review DR performance and document lessons learned.
    * Plan the failback process when the primary region is restored.


---


## Source: ops/dr/oci_dr_runbook.md

# OCI Disaster Recovery Runbook for Golden Platform

## Scope
Covers critical components of the Golden Platform microservices platform:
* OKE (Oracle Kubernetes Engine) clusters (for all microservices and Backstage IDP)
* Autonomous DB / DB Systems (for **Backstage PostgreSQL persistence**)
* Object Storage (for state and assets)
* OCI Container Registry (OCIR)

## RPO / RTO
* RPO (target, not yet tested): 15 minutes (via automated backups and cross-region replication).
* RTO (target, not yet tested): 1–2 hours for full region failover of all microservices.

## Strategy
* Infrastructure as Code: OKE cluster and networking managed via **Terraform** (multi-region capable).
* Database: **Backstage PostgreSQL** data protected via cross-region replication or Autonomous DB failover mechanisms.
* Storage: Cross-region replication policies for Object Storage.
* Image Management: OCIR replication policies to secondary region.
* Deployment: Application restoration managed entirely via **GitOps** (ArgoCD/Flux).

## Steps (Region Failover)
1. **Identify Disaster Event**
    * Confirm primary region outage and activate communications plan.
2. **Database Recovery**
    * Restore Backstage DB from backups or activate standby/replica in the DR region.
    * Update connection secrets/credentials in OCI Vault (if needed).
3. **Provision OKE in DR Region**
    * Run Terraform against DR variables to stand up the OKE cluster, networking, and load balancers.
4. **GitOps Deploy**
    * Configure ArgoCD/Flux to use DR OKE context.
    * **Redeploy all Helm charts from Git**, ensuring the Backstage chart and microservices deploy successfully.
5. **DNS / Traffic Cutover**
    * Update DNS and any global load balancers to point to DR endpoints.
    * Validate connectivity and execute Post-Deployment Checklist.
6. **Monitor & Validate**
    * Monitor SLOs and error budgets; ensure systems are stable.
7. **Failback Planning**
    * Once primary region is stable, plan migration back with minimal downtime.


---


## Source: ops/on-call/escalation_paths.md

# Escalation Paths for Golden Platform

## Severity Levels
*P1 – Critical*
- Full outage of **Golden Platform microservices** or **Backstage IDP**; major **PostgreSQL** data corruption/loss; confirmed security breach.
- Escalation:
1. Primary on-call
2. Secondary on-call
3. SRE / Platform Lead
4. Incident Manager / Duty Exec

*P2 – High*
- Partial outage of core services; **SLO breach** (e.g., high latency, Backstage Catalog ingestion lagging); **PostgreSQL** performance degradation.
- Escalation:
1. Primary on-call
2. Secondary on-call
3. Service Owner / Relevant Engineering Team Lead

*P3 – Medium*
- Degraded non-critical service (e.g., non-core Backstage plugin); non-urgent bug or failure in a secondary system.
- Escalation:
1. Primary on-call (during business hours)
2. Product / Engineering team

*P4 – Low*
- Cosmetic issues, low-priority tickets, or minor documentation discrepancies.

## Communication Channels
- PagerDuty / OpsGenie / custom webhook from Prometheus/Grafana (for automated alerts).
- Slack / Teams incident channel (e.g., #inc-<date>-<short-desc> ).
- Email summary to stakeholders for P2 and higher post-mortem.


---


## Source: ops/on-call/on_call_policy.md

# On-Call Policy for Express Web Platform

## Objectives
- Ensure 24/7 coverage for **Golden Platform microservices** and the **Backstage IDP**.
- Minimize mean-time-to-detect (MTTD) and mean-time-to-resolve (MTTR) for platform issues.
- Provide a humane, sustainable rotation for engineers.

## Coverage Model
- Primary on-call: 1 engineer (Responsible for first response and mitigation)
- Secondary on-call: 1 engineer (Responsible for complex diagnosis and escalation support)
- Shadow on-call (optional, trainees)

## Expectations
- Acknowledge P1 (Critical) pages within 5 minutes, initiating the defined **P1 Escalation Path**.
- Acknowledge P2 (High) pages within 15 minutes, initiating the defined **P2 Escalation Path**.
- Utilize the official runbooks in `/ops/playbooks` and `/ops/dr` for incident resolution.
- All changes for mitigation must go through **GitOps (ArgoCD/Flux)** where technically feasible, ensuring auditability.
- Avoid direct production changes unless under documented 'break-glass' protocol.

## Handover
- Daily handoff notes recorded in Slack / Teams, summarizing shift status.
- Review all open incidents, ongoing investigations, and high-risk platform areas during the handoff meeting.
- Confirm next on-call engineer has access to all required tooling and documentation.


---


## Source: ops/playbooks/README.md

# Operational Playbooks for Golden Platform

This directory contains tactical, step-by-step procedures (**Playbooks**) designed to standardize routine and emergency operational tasks across the Golden Platform microservices and Backstage IDP infrastructure. Adherence to these playbooks minimizes operational risk and ensures predictable outcomes.

## Available Playbooks

| Playbook File | Operational Task | Applies To |
| :--- | :--- | :--- |
| [db_failover_postgres.md](../ops/runbooks/playbooks/db_failover_postgres.md) | Executing a controlled failover from the primary PostgreSQL instance to a synchronous replica. | Backstage IDP, Core Microservices |
| [cache_warmup_redis.md](../ops/runbooks/playbooks/cache_warmup_redis.md) | Standardized procedure for pre-filling critical application caches after deployment or service restart. | Microservices using Redis |
| [queue_drain_kafka.md](../ops/runbooks/playbooks/queue_drain_kafka.md) | Safely stopping Kafka consumers during maintenance or deployment to prevent data loss or duplicate processing. | Async Microservices (Kafka) |
| [deployment_rollback_gitops.md](../ops/runbooks/playbooks/deployment_rollback_gitops.md) | Executing a verified, safe rollback to a known-good state using GitOps tooling (ArgoCD/Flux). | All Application Deployments |


---


## Source: ops/playbooks/cache_warmup_redis.md

# Redis Cache Warm-Up Playbook for Golden Platform Microservices

## Goals
- Avoid cold-start performance degradation after deployment or restart of core services.
- Pre-populate high-value keys for the Golden Platform service and relevant Backstage plugins.

## Steps

1. **Confirm Deployment Stability**
- Wait until all application pods (especially those relying on Redis) are **Ready** and passing Liveness/Readiness probes.
- Verify that the Redis service itself is stable and accessible.

2. **Execute Warm-Up Job (Kubernetes)**
- Run the dedicated `redis-warmup-job.yaml` (or equivalent script) as a one-off Kubernetes Job.
- This script must target key API endpoints (e.g., core T2S functions, Backstage Catalog APIs) to force data loading into the cache.

3. **Monitor Cache Performance**
- Check Redis command rate (`INFO STATS`) to confirm data loading activity.
- Monitor **Cache Hit Ratio** and aim for the target threshold (e.g., >95%) before proceeding.
- Validate application latency using monitoring dashboards while the job is running.

4. **Clean Up**
- Once the cache hit ratio is acceptable, confirm the Warm-Up Job has completed successfully and delete the Kubernetes Job resource to avoid resource waste.

5. **Automate/Integrate**
- Integrate the warm-up job execution into the deployment pipeline as a **post-deployment hook** in your GitOps configuration (ArgoCD/Flux) to ensure it runs on every relevant deployment.


---


## Source: ops/playbooks/db_failover_postgres.md

# PostgreSQL Database Failover Playbook for Backstage IDP

## Goals
- Execute a controlled failover of the primary Backstage PostgreSQL database with minimal downtime and data loss.
- Ensure application services quickly reconnect to the new primary instance.

## Preconditions
- Managed service (e.g., AWS RDS, Azure Database for PostgreSQL, Cloud SQL) or self-managed with streaming replication.
- At least one healthy, synchronized read replica available in the primary or DR region.

## Steps

1. **Confirm Incident and Backup**
- Check metrics: replication lag, active connections, and primary errors.
- Validate that the primary is truly unhealthy or confirm a pre-planned failover.
- **Verify the status and time of the last successful backup.**

2. **Isolate Primary and Promote Replica**
- Temporarily scale down/block traffic to the old primary instance.
- For managed DB: Use console/CLI to promote the designated read replica to the new primary instance.
- For self-managed: Run `pg_ctl promote` or equivalent on the replica host.

3. **Update Kubernetes Configuration (GitOps)**
- **Update connection endpoints/credentials** in the central source of truth:
- **Kubernetes Secrets** (if storing credentials externally).
- **ConfigMap Generation Source** (to update the host if needed).
- Trigger the **GitOps deployment** to propagate the new connection string to the Backstage deployment.

4. **Verify Application Health**
- Run application smoke tests against core Golden Platform services.
- Check the Backstage health status (`/healthcheck` endpoint).
- **Confirm Backstage Catalog Entities are being processed** without database connection errors.
- Monitor application error rates and latency via observability dashboards.

5. **Post-Failover Tasks**
- Plan re-seeding or re-adding the old primary as a replica or standby instance if the host is healthy.
- Document the incident timeline and performance metrics during the failover window.


---


## Source: ops/playbooks/deployment_rollback_gitops.md

# Deployment Rollback with GitOps for Golden Platform

## Principles
* Rollbacks must be executed by reverting the Git commit or applying a known-good Helm chart tag.
* Direct manual changes (`kubectl edit` or `kubectl apply`) to production resources are strictly forbidden.
* The Git repository is the single source of truth for the desired state.

## Steps

1. **Identify Bad Change & Impact**
* Determine the specific commit, PR, or Helm chart value change that introduced the issue.
* Correlate the change with a failure in **SLOs**, Liveness/Readiness probes, or high error rates.
* Review ArgoCD/Flux events for the failing application (e.g., Backstage chart).

2. **Execute Git Revert**
* Use `git revert <commit-id>` or switch the GitOps target to a previous, known-good tag/commit.
* **Ensure the reverted state includes working Helm chart values.**

3. **Push to Main/Target Branch**
* Create and merge the rollback PR quickly (following the P1/P2 communication protocol).

4. **Observe Reconciliation & Stabilization**
* ArgoCD/Flux will automatically detect the Git change and:
    * Apply the previous stable manifests (e.g., older Helm chart version).
    * Restore the working application version.
* **Monitor Kubernetes resources** (Deployment/StatefulSet) to ensure old pods terminate and new stable pods become **Ready**.
* **Verify Application Health** by checking the `/healthcheck` endpoint for Backstage or core T2S microservices.

5. **Post-Rollback**
* Document the root cause analysis, including the time-to-revert (TTR).
* Update the incident ticket with the successful rollback outcome.
* Create a follow-up task to address the root cause and prevent recurrence.


---


## Source: ops/playbooks/queue_drain_kafka.md

# Kafka Queue Drain Playbook for Golden Platform Microservices

## When to Use
- Before deploying breaking schema or code changes to consumers.
- Before performing maintenance or scaling down Kafka brokers/clusters.

## Steps

1. **Pause Consumers (Kubernetes/Helm)**
- Use Helm/GitOps tooling to **scale the deployment replicas of the target consumer to 0** (`replicaCount: 0`).
- **Verify** that the consumer group is no longer actively consuming messages.
- *Alternative:* If using internal application controls, use consumer group pause functionality if available in the client library.

2. **Verify Queue Drain State**
- **Crucial Check:** Confirm that the consumer group **lag is zero** or messages are not actively building up. Use a tool like `kafka-consumer-groups.sh` or a dedicated monitoring dashboard.
- Allow any in-flight messages (Option B) to finish processing before proceeding.
- If necessary, run a temporary consumer (Option A) that reads and discards remaining messages to hit zero lag.

3. **Deploy New Consumer Version (GitOps)**
- Update the image tag/chart values in Git.
- Allow ArgoCD/Flux to deploy the updated consumer version while replicas remain at 0.
- **Verify** the new Deployment/StatefulSet template is ready for scaling.

4. **Resume Consumption and Monitor**
- Use Helm/GitOps to **scale consumer replicas back up** to the desired count.
- **Monitor lag** immediately to ensure consumers are catching up quickly.
- Monitor error rates, processing time, and application logs for any issues introduced by the new version.


---


## Source: ops/rbac/README.md

# Role-Based Access Control (RBAC) for Golden Platform

This folder contains production-oriented RBAC templates for Kubernetes, ensuring compliance with **least privilege** principles and supporting **SOC 2 control** objectives. Access is segmented based on operational need for the Golden Platform microservices and the Backstage IDP infrastructure.

## Core Principles

* **Least Privilege:** Users and service accounts are granted only the permissions essential to perform their required tasks.
* **Auditability:** All production access is tracked, logged, and reviewed.
* **No Cluster-Admin:** Direct `cluster-admin` access is restricted to break-glass scenarios only.

## Defined Roles

| Role | Primary Responsibilities | Access Level Summary | Template Example |
| :--- | :--- | :--- | :--- |
| **SRE / Platform** | Incident response, infrastructure management, GitOps tool administration. | Full control over Namespace resources, exec access to specific platform pods (e.g., PostgreSQL for debug). | [`k8s_rbac_sre.yaml`](../ops/runbooks/rbac/k8s_rbac_sre.yaml) |
| **App Developers** | Deploying/managing their own microservices, viewing logs/metrics. | CRUD (Create, Read, Update, Delete) on Deployment, Service, ConfigMap for *their* Namespace; Read-only for other infrastructure. | (Template not included, but defined) |
| **Read-only Observers** | Auditing, monitoring, troubleshooting by viewing resources. | Read-only access to most resources (Pods, Events, Logs, Services) across non-sensitive Namespaces. | [`k8s_rbac_readonly.yaml`](../ops/runbooks/rbac/k8s_rbac_readonly.yaml) |


---


## Source: robotics/README.md

# Agentic Clinical Safety: Autonomous Protocols for Surgical Robotics

## The Challenge: Operational Fragility in Connected Medicine

As medical robotics move from isolated hardware to cloud-connected agentic systems, the risk isn't just downtime—it's **operational fragility**. In a surgical environment, a 3-second desync due to network jitter or latent mechanical stress isn't just a 404 error; it represents a critical safety risk and an average loss of **$7,900 per minute** in surgical theater downtime.

## The Solution: Predictive Self-Healing Infrastructure

This domain within the **Golden Platform** serves as a specialized "Safety Guardrail" for medical robotics and EHR-integrated systems. By utilizing **Agentic AI**, the platform moves beyond reactive alerts to autonomous intervention.

### Core Capabilities:

* **Kinematic Telemetry Analysis:** Monitoring robotic joint stress, motor temperature, and torque in real-time.
* **Latency-Correlation Engines:** Using **TCN (Temporal Convolutional Networks)** to detect the subtle relationship between network jitter and mechanical desynchronization before they impact the procedure.
* **Autonomous Sidecar Agents:** Specialized agents that can instantly intercept failing telemetry packets and reroute traffic to **Local Edge Compute** gateways.
* **Safe-State Transitioning:** Gracefully transitioning a robotic system to a "Safe Manual" mode or local-only control the moment an infrastructure failure is predicted.

---

## Directory Overview

* **`/simulator`**: Contains the `clinical_fragility_gen.py` script which generates high-fidelity synthetic telemetry for surgical robotic arms.
* **`/agents`**: Logic for the autonomous interceptors that handle real-time traffic rerouting.
* **`/proto`**: gRPC definitions for low-latency, clinical-grade data streaming.

## The "Golden Demo": Clinical Fragility Simulation

The included simulator demonstrates a **"Latent Failure"** scenario:

1. The system identifies a creeping increase in network Round-Trip Time (RTT).
2. Simultaneously, it detects microscopic vibrations in a robotic joint.
3. While standard monitoring tools would stay "Green," our **AIOps Engine** flags this as a **FRAGILE** state and triggers an autonomous failover to ensure surgical continuity.

---

**Author:** [Rev. Dr. Emmanuel Naweji](https://www.emmanuelnaweji.com/)
*Focusing on the intersection of Autonomous Reliability and Clinical Safety.*


---


## Source: src/golden/robotics/grpc/README.md

### **gRPC Infrastructure README (`src/golden/robotics/grpc/README.md`)**

Use the following content to explain how your [surgical_server.py](../src/golden/robotics/grpc/surgical_server.py) and [surgical_client.py](../src/golden/robotics/grpc/surgical_client.py) function as the nervous system of your platform:

---

# Clinical gRPC: Low-Latency Telemetry Nervous System

## The Challenge: The "Last-Mile" Jitter Gap

In [connected medical robotics](../src/golden/robotics), standard REST or JSON-over-HTTP protocols introduce overhead that can lead to kinematic desynchronization. Even a short cloud disconnect can disrupt a [surgical workflow](../src/golden/robotics).

## The Solution: Bi-Directional gRPC Streams

This directory houses the [gRPC implementation](../src/golden/robotics/grpc) of our [surgical_telemetry.proto](../proto/surgical_telemetry.proto). By utilizing **HTTP/2 bi-directional streaming**, we aim for the low, consistent latency that [surgical robotics](../src/golden/robotics) needs (end-to-end latency has not been benchmarked).

### Components:

* **`surgical_server.py`**: The central hub that processes [high-fidelity telemetry](../proto/surgical_telemetry.proto) and issues autonomous [safety commands](../proto/surgical_telemetry.proto).
* **`surgical_client.py`**: A simulator for the robotic end-effector, sending continuous kinematic data and reacting to [EMERGENCY_STOP](../src/golden/robotics/agents/emergency_stop_handler.py) or [REROUTE_TO_EDGE](../src/golden/robotics/edge/edge_gateway_config.yaml) signals.

## Deployment Instructions

To demonstrate the [self-healing](../README.md) clinical loop:

1. **Start the Server**:
```bash
python3 surgical_server.py

```


2. **Launch the Robot Client**:
```bash
python3 surgical_client.py

```



---

**Strategic Value:** This setup demonstrates how, under [network jitter](../src/golden/robotics), the [Golden Platform](../README.md) is designed to keep a safety channel (EMERGENCY_STOP / REROUTE_TO_EDGE) to the clinical device. This is a simulation, not a validated medical device.



---


## Source: sre/README.md

# DevSecOps & Identity Governance

This directory contains the "Security-as-Code" implementations that enforce a **Zero Trust** architecture. It focuses on automated Identity and Access Management (IAM), ensuring that the principle of "Least Privilege" is programmatically enforced across the platform.

### 1. Identity Lifecycle Automation
* **Files:** `scim-provisioning.sh`, `sso-integration-guide.md`
* **Core Functionality:** Implements **System for Cross-domain Identity Management (SCIM)** to automatically provision and de-provision user accounts based on HR signals. It also standardizes **Single Sign-On (SSO)** integration for all platform tools.
* **SRE Challenge Solved:** **Onboarding Toil & Zombie Accounts.** Eliminates the manual ticket-based work of creating users and ensures that when an employee leaves, their access is revoked instantly across all systems.
* **Operational Impact:** Reduces access governance risks and ensures immediate compliance with **SOC 2** and **ISO 27001** offboarding requirements.

### 2. Access Control Strategy
* **Files:** `reliability-rbac-model.md`
* **Core Functionality:** Defines the **Role-Based Access Control (RBAC)** matrix for the platform. It maps engineering roles (e.g., "Junior Dev," "Senior SRE") to specific Kubernetes ClusterRoles and cloud IAM permissions.
* **SRE Challenge Solved:** **Permission Bloat.** Prevents the dangerous anti-pattern of giving everyone "Admin" access just to make things work.
* **Operational Impact:** Minimizes the **Blast Radius** of compromised credentials or insider threats by strictly enforcing Least Privilege access.

### 3. Automated Policy Enforcement
* **Files:** `mfa-policy-setup.sh`
* **Core Functionality:** A compliance script that audits and enforces **Multi-Factor Authentication (MFA)** settings across cloud providers (AWS/GCP/Azure) and SaaS tools (GitHub/GitLab).
* **SRE Challenge Solved:** **Configuration Drift.** Ensures that security settings don't degrade over time due to manual changes or exceptions.
* **Operational Impact:** Hardens the "front door" of the infrastructure, protecting against credential stuffing attacks and satisfying cyber-insurance mandates.

---
**Summary:** This module shifts security left, treating Access Governance not as a bureaucracy, but as an automated reliability feature that scales with the organization.


---


## Source: ops/sre/aiops/README.md

# AIOps Intelligence Layer

This directory contains the core machine learning scripts that drive the **Predictive Reliability** capabilities of the platform.

### 1. `log-pattern-cluster.py`
* **Core Functionality:** Utilizes **Natural Language Processing (NLP)** techniques to structure unstructured data. It converts raw text logs (e.g., "timeout connecting to db") into numerical vectors using `TfidfVectorizer` and groups them using the `KMeans` clustering algorithm.
* **SRE Challenge Solved:** **Alert Fatigue & Root Cause Analysis.** rapidly correlates thousands of log lines into distinct patterns. A sudden spike in a specific cluster instantly identifies a systemic issue (e.g., database connectivity) without manual parsing.
* **Operational Impact:** Drastically reduces **Mean Time to Detection (MTTD)** by automatically converting high-volume log noise into clear, actionable signals.

### 2. `anomaly-detection-run.py`
* **Core Functionality:** Implements statistical models (Isolation Forests / Z-Score) to analyze real-time system metrics (CPU, Memory, Latency) and flag deviations.
* **SRE Challenge Solved:** **Proactive Incident Management.** Unlike static thresholds (e.g., "Alert if CPU > 80%"), this detects "unknown unknowns"—such as a service idling at 10% when it normally operates at 40%—catching silent failures before they impact users.

### 3. `forecasting-model.py`
* **Core Functionality:** Deploys time-series forecasting models (ARIMA, Prophet, or LSTM) to predict future metric values based on historical telemetry.
* **SRE Challenge Solved:** **Strategic Capacity Planning.** Shifts operations from reactive scaling to predictive resource management (e.g., "Based on current trends, disk space will be exhausted in 4 days").

### 4. `autoscaling-ml-recommender.py`
* **Core Functionality:** Ingests output from the forecasting model to generate actionable infrastructure configurations, specifically recommending `minReplicas` and `maxReplicas` for the Kubernetes HPA.
* **SRE Challenge Solved:** **Cost Optimization & Performance.** Ensures the infrastructure scales up *before* traffic spikes occur (preventing latency) and scales down immediately when demand drops (eliminating waste).

---
**Summary:** These components form the **"AIOps Engine,"** successfully transitioning operations from a **Reactive** model (remediating failure) to a **Predictive** model (anticipating risks).


---


## Source: ops/sre/chaos/README.md

# Chaos Engineering & Resilience Suite

This directory contains the **Resilience Validation Framework** used to proactively test system stability. These scripts are executed as part of the CI/CD pipeline and scheduled maintenance windows to enforce "Anti-Fragile" architecture.

### 1. `pod-kill-test.sh`
* **Core Functionality:** Randomly terminates running Kubernetes pods within targeted namespaces using `kubectl delete pod` with randomized grace periods.
* **SRE Challenge Solved:** **Statelessness Verification.** Validates that microservices effectively handle sudden termination without data loss or user session interruption, ensuring true horizontal scalability.
* **Operational Impact:** Confirms that `replicaSets` and HPA (Horizontal Pod Autoscalers) react correctly to unexpected process failures, maintaining service availability.

### 2. `node-failure-test.sh`
* **Core Functionality:** Simulates underlying infrastructure failure by cordoning and draining nodes, or forcibly terminating worker node instances via cloud provider CLIs (AWS CLI/gcloud).
* **SRE Challenge Solved:** **Infrastructure Redundancy.** Tests the cluster’s ability to reschedule workloads to healthy nodes without service downtime.
* **Operational Impact:** Verifies that **PodDisruptionBudgets (PDBs)** are correctly configured and that capacity planning allows for the loss of a compute node during peak loads.

### 3. `network-latency-injection.sh`
* **Core Functionality:** Uses traffic control tools (like `tc` or service mesh fault injection) to introduce artificial latency and packet loss between microservices.
* **SRE Challenge Solved:** **Timeout & Retry Logic.** Exposes hidden dependencies and "cascading failure" risks where a slow downstream service causes upstream request queues to fill up.
* **Operational Impact:** Validates that circuit breakers and timeout thresholds are correctly tuned, preventing a minor network blip from becoming a system-wide outage.

### 4. `dependency-failure-simulation.sh`
* **Core Functionality:** Blocks access to critical external dependencies (e.g., DNS, databases, or third-party APIs) via network policies or mock responses.
* **SRE Challenge Solved:** **Graceful Degradation.** Ensures the application can still serve core functionality (or fail with a user-friendly error) when non-essential dependencies go dark.
* **Operational Impact:** Enforces "Zero Trust" resilience, ensuring that a failure in a 3rd-party API does not crash the entire platform.

### 5. `region-failover-test.sh`
* **Core Functionality:** Simulates a complete regional outage by routing traffic away from the primary region to a secondary standby region (DR).
* **SRE Challenge Solved:** **Disaster Recovery (DR) Readiness.** Validates the RTO (Recovery Time Objective) and RPO (Recovery Point Objective) of the global architecture.
* **Operational Impact:** proves the effectiveness of multi-region active-active or active-passive setups, ensuring business continuity during catastrophic cloud provider outages.

---
**Summary:** This suite implements **Continuous Verification**, moving beyond "hoping" systems are resilient to mathematically proving they can withstand production turbulence.


---


## Source: ops/sre/observability/README.md

# Unified Observability & Telemetry Ecosystem

This directory contains the configurations and automation scripts for a full-stack observability pipeline. It implements the "Three Pillars of Observability" (Logs, Metrics, Traces) while integrating **OpenTelemetry** standards to ensure vendor neutrality and deep system visibility.

### 1. OpenTelemetry Implementation (`opentelemetry-*`)
* **Files:** `opentelemetry-collector-start.sh`, `opentelemetry-tracing-setup.md`
* **Core Functionality:** Deploys and configures the **OpenTelemetry (OTel) Collector** as a sidecar or daemonset to ingest traces and metrics from application microservices.
* **SRE Challenge Solved:** **Vendor Lock-in & Fragmented Tracing.** Decouples instrumentation from the backend storage, allowing telemetry data to be routed to multiple destinations (e.g., Prometheus, Jaeger, Datadog) without code changes.
* **Operational Impact:** Enables **Distributed Tracing** across polyglot boundaries, allowing engineers to visualize the entire request lifecycle through the stack.

### 2. Datadog Integration Suite (`datadog-*`)
* **Files:** `datadog-agent-install.sh`, `datadog-apm-setup.md`
* **Core Functionality:** Automates the deployment of the Datadog Agent and Application Performance Monitoring (APM) libraries across the Kubernetes cluster.
* **SRE Challenge Solved:** **Infrastructure-Application Gap.** Bridges the divide between raw infrastructure metrics (CPU/Memory) and application-level performance (Throughput/Latency).
* **Operational Impact:** Provides instant "Single Pane of Glass" visibility, reducing context switching during incidents by correlating infrastructure health directly with service performance.

### 3. Log Correlation Engine (`log-correlation-*`)
* **Files:** `log-correlation-tool.sh`, `log-correlation-design.md`
* **Core Functionality:** Injects unique `TraceIDs` and `SpanIDs` into structured logs (JSON format) to bind them to specific distributed traces.
* **SRE Challenge Solved:** **"Needle in a Haystack" Debugging.** Solves the issue of searching through millions of disjointed logs during an outage.
* **Operational Impact:** Drastically lowers **MTTR (Mean Time to Resolution)** by allowing engineers to jump from a slow trace span directly to the exact error logs generated by that specific request.

### 4. Digital Experience Monitoring (`synthetic-*`, `rum-*`)
* **Files:** `synthetic-test-run.sh`, `rum-and-synthetic-tests.md`
* **Core Functionality:** Configures **Synthetic Probes** (API tests, browser tests) and **Real User Monitoring (RUM)** to validate system health from the user's perspective.
* **SRE Challenge Solved:** **Silent Failures.** Detects issues where the backend is "green" (healthy metrics) but the frontend user experience is broken (e.g., login failure).
* **Operational Impact:** Enforces **SLA/SLO Compliance** by validating availability from outside the network, ensuring the platform meets business uptime guarantees.

---
**Summary:** This module moves the platform beyond simple "up/down" monitoring to **Deep Observability**, providing the granular data needed for the AIOps engine to make accurate predictions.


---


## Source: ops/sre/observability/datadog-apm-setup.md

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
  [tags.datadoghq.com/service](https://tags.datadoghq.com/service): "apps/workload" # Service name in APM
  [tags.datadoghq.com/env](https://tags.datadoghq.com/env): "production" # Environment filter
  [tags.datadoghq.com/version](https://tags.datadoghq.com/version): "1.0.0" # Version for deployment tracking


---


## Source: ops/sre/observability/log-correlation-design.md

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


## Source: ops/sre/observability/opentelemetry-tracing-setup.md

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


## Source: ops/sre/observability/rum-and-synthetic-tests.md

# Real User Monitoring (RUM) & Synthetic Testing Strategy

## 1. Overview
This document defines the frontend observability standards for the Express AIOps platform. We utilize a dual-approach strategy:
1. **RUM (Real User Monitoring):** Captures *actual* user experience, including JavaScript errors, network latency, and session replays.
2. **Synthetic Testing:** Simulates user journeys and API calls from global locations to proactively detect downtime before real users are impacted.

---

## 2. Real User Monitoring (RUM)

We use the Datadog RUM SDK to instrument the frontend React/Express application.

### Initialization
The RUM client must be initialized in the main entry point of the frontend application (e.g., `index.js` or `App.tsx`).

```javascript
import { datadogRum } from '@datadog/browser-rum';

datadogRum.init({
    applicationId: process.env.REACT_APP_DD_RUM_APP_ID,
    clientToken: process.env.REACT_APP_DD_CLIENT_TOKEN,
    site: 'datadoghq.com',
    service: 'nrp-frontend',
    env: process.env.NODE_ENV || 'production',
    version: process.env.REACT_APP_VERSION,
    sessionSampleRate: 100,
    sessionReplaySampleRate: 20, // Record 20% of sessions for replay
    trackUserInteractions: true,
    trackResources: true,
    trackLongTasks: true,
    defaultPrivacyLevel: 'mask-user-input',
});

datadogRum.startSessionReplayRecording();


---


## Source: ops/sre/reliability/README.md

# Reliability Engineering Center of Excellence

This directory serves as the operational playbook and tooling repository for the **Reliability Engineering** function. It codifies the practices of Service Level Objectives (SLOs), Incident Management, and "Anti-Fragile" operations.

### 1. Service Level Objectives (SLO) Management
* **Files:** `slo-burn-check.sh`, `error-budget-consume.sh`, `datadog-slo-chaos-cheatsheet.md`
* **Core Functionality:** Automated scripts to monitor **Error Budget Burn Rates**. The `slo-burn-check.sh` script alerts the team when burn rate thresholds (e.g., burning 2% of budget in 1 hour) are exceeded.
* **SRE Challenge Solved:** **Alert Fatigue.** Moves alerting from "My server CPU is high" (which might not matter) to "My customers are seeing too many errors" (which always matters).
* **Operational Impact:** Enables **Data-Driven Prioritization**, allowing development teams to push features when the budget is healthy and forcing reliability freezes when the budget is exhausted.

### 2. Incident Command & Response
* **Files:** `incident-simulator.sh`, `sre-scenario-playbook.md`
* **Core Functionality:** Tools for running **Game Days** and **Chaos Engineering** drills. `incident-simulator.sh` generates synthetic failure signals to train on-call engineers on the incident response lifecycle.
* **SRE Challenge Solved:** **Unpreparedness.** ensures that the first time an engineer sees a major outage isn't at 3 AM during a real fire.
* **Operational Impact:** Reduces **MTTR (Mean Time to Resolution)** by building muscle memory and validating runbooks before they are needed in production.

### 3. Architecture & Governance
* **Files:** `reliability-architecture.md`, `reliability-center-overview.md`
* **Core Functionality:** The "Constitution" of the platform. Defines the **Reliability Standards** (e.g., "All Tier-1 services must have active-active failover") and governance models.
* **SRE Challenge Solved:** **Architectural Drift.** Provides a clear standard against which new microservices are audited before going to production (Production Readiness Review).
* **Operational Impact:** Enforces **Quality at Source**, preventing unreliable code from ever reaching production environments.

### 4. Operational Cheat Sheets
* **Files:** `go-okta-terraform-microcheatsheet.md`
* **Core Functionality:** Quick-reference guides for complex operational tasks involving authentication (Okta) and infrastructure provisioning (Terraform).
* **SRE Challenge Solved:** **Cognitive Load.** Reduces the need for engineers to memorize complex CLI commands or API schemas during stressful debugging sessions.
* **Operational Impact:** Speeds up **triage and remediation** by putting the right commands at the engineer's fingertips.

---
**Summary:** This module is the "Brain" of the SRE practice, transforming Reliability from a vague concept into a measurable, engineering-driven discipline.
```


---


## Source: ops/sre/reliability/datadog-slo-chaos-cheatsheet.md

# Datadog, SLO, and Chaos Engineering Mastery Sheet
Senior SRE Preparation – Streaming and High-Traffic Systems

## 1. Datadog Cheat Sheet

### Key Components

**APM (Traces)**
- Service maps
- Latency breakdowns
- Dependency analysis
- Request-level performance during peak traffic

**Metrics**
- CPU, memory, request throughput
- Error rate and saturation
- Video playback or key business metrics

**Logs**
- Structured logs
- Log pipelines and parsing
- Trace-to-log correlation

**Dashboards**
- SLO dashboards
- Latency heatmaps
- Playback/transaction health monitoring

**RUM (Real User Monitoring)**
- Page load
- Stream or transaction quality
- Buffering / UX-impacting events

**Synthetic Tests**
- Pre-peak, mid-peak, and post-peak availability tests
- API uptime monitoring

**Watchdog (ML)**
- Outlier and anomaly detection
- Pattern recognition during traffic spikes

### Senior-Level Talking Points

- “I create Datadog observability packs that standardize dashboards, alerts, and tracing patterns across teams.”
- “I use burn-rate alerts instead of raw threshold alerts to tie monitoring to SLOs and user experience.”
- “I rely on APM + RUM to detect performance regressions during peak traffic windows.”
- “I design synthetic tests for critical user journeys and run them before and during major events.”
- “I leverage Watchdog insights to detect anomalies before they escalate into incidents.”

---

## 2. SLO and Error Budget Cheat Sheet

### Example SLOs

- **Stream start / API response SLO:** 99% complete under 3 seconds.
- **Buffering / failure ratio SLO:** Less than 0.5% of total session time.
- **Error rate SLO:** Less than 0.1% of user-visible failures.
- **Critical API latency SLO:** P95 under 200 ms.
- **Event window uptime SLO:** 99.99% uptime during defined critical windows.

### How to Talk About SLOs

- Define SLOs from the **user’s perspective**, not just node or pod metrics.
- Identify SLIs first (latency, error rate, availability, buffering, success rate).
- Use SLOs to guide:
  - Alerting (burn rates).
  - Deployment gates (freeze when error budget is consumed).
  - Product trade-offs (shipping vs hardening).
- Integrate SLO dashboards into team retros and operational reviews.

### Error Budget Rules of Thumb

- 14x burn → Immediate page (something is seriously wrong).
- 4x burn → Notify engineering leadership.
- 2x burn → Engage product to align priorities (features vs reliability).

---

## 3. Chaos Engineering Cheat Sheet

### Common Experiments

- Node failure simulation.
- Pod kill tests.
- Region or AZ failover.
- Network latency injection.
- Packet loss simulation.
- Cache or database dependency failures.
- Traffic surge / spike tests.
- DNS degradation tests.

**Positioning line:**

> “I run hypothesis-driven chaos experiments to validate SLOs, uncover unknown failure modes, and ensure the user experience remains stable even under failure conditions.”

---

## 4. Go / Okta / Terraform Micro-Cheat Sheet

See `go-okta-terraform-microcheatsheet.md` in this folder for language/tool-specific talking points and patterns.

---

## 5. Usage in This Repo

This cheat sheet backs the `sre/` scripts and is used as:
- A “prep deck” for interviews.
- An internal SRE consultancy guide.
- A training reference for teams learning Datadog, SLOs, and chaos engineering.

---


## Source: ops/sre/reliability/go-okta-terraform-microcheatsheet.md

## Using Okta with Terraform (example configs).


---


## Source: ops/sre/reliability/reliability-architecture.md

## Reliability Architecture integrated with GitOps, OTel, SLOs, multi-cloud failover.


---


## Source: ops/sre/reliability/reliability-center-overview.md

## Central dashboard for SLOs, incidents, forecasts, and AI-driven reliability.


---


## Source: ops/sre/reliability/sre-scenario-playbook.md

## Walkthrough of production-grade SRE scenarios.


---


## Source: ops/sre/security/reliability-rbac-model.md

## RBAC aligned with Zero-Trust and GitOps-only changes.


---


## Source: ops/sre/security/sso-integration-guide.md

## SSO guide for Okta, Azure AD, Google IdP.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
