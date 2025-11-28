# AIOps & Predictive Resilience Engine (/ai)

**The Nervous System of the Express Platform**

This directory contains the **Autonomous Reliability Agents** and **Deep Learning Models** that power the platform's self-healing capabilities. It transforms raw telemetry into actionable remediation plans using a continuous *Observe-Analyze-Plan-Execute* control loop.

---

## Autonomous Agent Architecture

The system is composed of four decoupled agents, coordinated by a central **Orchestrator** (`orchestrator.py`).

| Agent | Role | Logic & Responsibilities |
| :--- | :--- | :--- |
| **Observer** | **The Eyes** | Collects real-time telemetry (Latency, CPU, Error Rates). Supports simulated noise generation for testing and pluggable adapters for **Prometheus/CloudWatch**. |
| **Analyzer** | **The Brain** | Detects anomalies using a hybrid approach:<br>1. **Deterministic:** Static thresholds (e.g., Latency > 200ms) defined in `agent_config.yaml`.<br>2. **Predictive:** PyTorch **LSTM & TCN models** that forecast SLI violations before they occur. |
| **Planner** | **The Logic** | Maps identified risks to remediation strategies. Uses a **Rule-Based Engine** to select the best action (e.g., "High Latency" $\to$ "Scale Up") and generates an audit trail (`plan_id`, `reasoning`). |
| **Executor** | **The Hands** | Safely applies changes to the infrastructure.<br>• **Dry Run Mode:** Simulates actions for safety.<br>• **Active Mode:** Executes real Kubernetes/Terraform commands.<br>• **Safety Rails:** Prevents cascading failures with strict action limits. |

---

## Predictive Modeling (PyTorch)

We utilize custom deep learning models to predict Service Level Objective (SLO) violations.

* **LSTM (Long Short-Term Memory):** Specialized for detecting temporal dependencies in sequential log data.
* **TCN (Temporal Convolutional Network):** Uses dilated convolutions to capture long-range patterns with parallelized training efficiency.

**Locations:**
* `models/lstm_model.py`: PyTorch LSTM implementation with persistence.
* `models/tcn_model.py`: TCN implementation with causal padding.

---

## ⚡ Remediation Engine

The remediation logic is **declarative** and **dynamic**. You can define new self-healing rules without changing Python code.

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
