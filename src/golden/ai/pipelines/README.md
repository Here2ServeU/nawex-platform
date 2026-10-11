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

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
