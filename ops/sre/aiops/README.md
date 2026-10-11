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

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
