# AIOps System (/ai)

This directory implements the AI-driven operations (AIOps) layer for the **Express AI-Driven Multi-Cloud Resilience Platform**.

## Structure

- `notebooks/`  
  Jupyter notebooks for SLI/SLO analysis, anomaly detection experiments, and model exploration.

- `pipelines/`  
  Python data pipelines for:
  - Loading metrics and SLO data
  - Engineering time-series features
  - Detecting anomalies
  - Training predictive models (LSTM, TCN)

- `models/`  
  PyTorch implementations of:
  - LSTMSLIPredictor
  - TCN (Temporal Convolutional Network)

- `remediation/`  
  - Declarative remediation rules (`remediation_rules.yaml`)
  - A remediation engine that can call `kubectl` or traffic-management tools.

- `agents/`  
  Multi-agent AIOps orchestrator:
  - ObserverAgent (collects metrics)
  - AnalyzerAgent (evaluates risk & anomalies)
  - PlannerAgent (maps conditions to remediation rules)
  - ExecutorAgent (applies actions)
  - `orchestrator.py` chaining them together.

## Quickstart

### 1. Install dependencies

Create a venv and install:

```bash
pip install pandas numpy torch pyyaml
```

(And `jupyter` if you want to run notebooks.)

### 2. Train models

From the repo root:

```bash
cd ai
python pipelines/train_lstm.py
python pipelines/train_tcn.py
```

This will:
- Generate synthetic SLI/SLO data
- Build rolling-window features
- Train an LSTM and TCN for latency prediction

### 3. Run the AIOps orchestrator

```bash
cd ai
python agents/orchestrator.py
```

By default the executor runs in **dry_run** mode (no real `kubectl` changes).  
Switch to `live` in `agents/agent_config.yaml` to enable actual remediation commands.

Use this directory as:
- A **teaching lab** for AIOps concepts
- A **demo** in interviews
- A **POC** starting point for client environments
