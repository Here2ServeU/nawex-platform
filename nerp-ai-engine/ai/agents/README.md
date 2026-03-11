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

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
