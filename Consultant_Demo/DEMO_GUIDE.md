# My Demo Script & Setup

## 1. The Story Arc

* **The Baseline:** "Here is the system running normally. Note the low latency and 100% success rate."
* **The Incident:** (Action: Run `simulate_incident.sh`) "I am now going to simulate a 'bad deployment' or traffic spike."
* **The Detection:** "Notice the immediate dip in our SLO (Service Level Objective) panel."
* **The Diagnosis:** "I'm drilling down into the heatmap. It's not a database issue; it's application saturation."

## 2. Architecture Talking Points
* **Pattern:** Sidecar pattern for observability.
* **Flow:** Prometheus scrapes Express app over Docker bridge network.
* **Real-world context:** "This mimics a K8s environment using sidecars or DaemonSets."

## 3. Grafana Panels (The "Expert" Setup)

### Panel 1: Event Loop Lag (Node.js Specific)
* **Query:** `nodejs_eventloop_lag_seconds`
* **Pitch:** "CPU is misleading in containerized Node. Event Loop Lag detects blocked threads before 504 timeouts happen."

### Panel 2: Apdex Score (Business Value)
* **Query:**
    ```promql
    (sum(rate(http_request_duration_seconds_bucket{le="0.1"}[1m])) + sum(rate(http_request_duration_seconds_bucket{le="0.5"}[1m]))) / 2 / sum(rate(http_request_duration_seconds_count[1m]))
    ```
* **Pitch:** "This tells management if users are happy (<100ms) without reading a graph."

### Panel 3: Latency Heatmap (The Wow Factor)
* **Query:** `sum(rate(http_request_duration_seconds_bucket[1m])) by (le)`
* **Format:** Heatmap
* **Pitch:** "Averages lie. This heatmap reveals the P99 outliers suffering 2-second delays."

## 4. Consultant Checks
* **"Why is there a data gap?"** -> Scrape interval miss or container restart. Fix: `absent()` alerts.
* **"How do we secure this?"** -> OAuth proxy (Google Auth) + TLS for scrape targets.
* **"Can we scale this?"** -> Thanos or Cortex for global querying and long-term storage.
