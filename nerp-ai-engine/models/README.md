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

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
