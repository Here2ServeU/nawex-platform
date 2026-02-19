# AIOps & Predictive Resilience Engine (/ai)

## The Nervous System of the Express Platform
This directory contains the **Autonomous Reliability Agents** and **Deep Learning Models** that power the platform's self-healing capabilities. It transforms raw telemetry into actionable remediation plans using a continuous *Observe-Analyze-Plan-Execute* control loop.

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

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
