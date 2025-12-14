# My Demo Script & Setup

## 1. The Story Arc
**Do not just show charts. Tell the story.**

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

## 4. Q&A "Consultant Checks"
* **"Why is there a data gap?"** -> Scrape interval miss or container restart. Fix: `absent()` alerts.
* **"How do we secure this?"** -> OAuth proxy (Google Auth) + TLS for scrape targets.
* **"Can we scale this?"** -> Thanos or Cortex for global querying and long-term storage.

---

### 2. Create the Chaos Scripts

Create a folder called `scripts` (or keep in root if you prefer) and add these two files.

**File:** `express-reliability-aiops-platform/normal_traffic.sh`

```bash
#!/bin/bash
echo "Generating healthy baseline traffic..."
URL="http://localhost:3000" # Ensure this matches your App port

while true; do
  # Simulating successful user behavior
  curl -s -o /dev/null -w "%{http_code} " "$URL/api/health"
  curl -s -o /dev/null -w "%{http_code} " "$URL/api/products"
  echo "."
  sleep 0.5 
done

```

**File:** `express-reliability-aiops-platform/simulate_incident.sh`

```bash
#!/bin/bash
echo "SIMULATING OUTAGE & LATENCY SPIKE..."
URL="http://localhost:3000"

# 1. Generate 404 Errors (Bad Link)
echo "Generating 404s..."
for i in {1..20}; do
   curl -s -o /dev/null "$URL/api/broken-endpoint" &
done

# 2. Generate Saturation
echo "Generating Saturation..."
for i in {1..50}; do
   curl -s -o /dev/null "$URL/api/products" &
done

echo "Batch sent. Watch the dashboard!"
```

**Important Action:** Make them executable by running this in your terminal:

```bash
chmod +x normal_traffic.sh simulate_incident.sh

```

---

### 3. Update Docker Compose (Port Fix)

You correctly identified a port conflict. Grafana defaults to 3000 internally. Since your App is on 3000, map Grafana to 3001.

**File:** `express-reliability-aiops-platform/docker-compose.yml`

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "3000:3000" # The Node App
    networks:
      - monitoring

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    networks:
      - monitoring

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000" # HOST 3001 maps to CONTAINER 3000
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    networks:
      - monitoring

networks:
  monitoring:
    driver: bridge

```

-----

### How to run the Demo
1. **Terminal 1:** `docker-compose up` (Get the system running).
2. **Terminal 2:** `./normal_traffic.sh` (Start this immediately to build history).
3. **Browser:** Open `localhost:3001` (Grafana) and `DEMO_GUIDE.md` (Your script).
4. **Terminal 3 (Ready):** Have `./simulate_incident.sh` typed out and ready to hit "Enter".
