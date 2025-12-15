# Consultant Demo Command Center

## Pre-Demo Checklist
1. **Start the Stack:**
Run the docker-compose up command in your terminal to start the services.
2. **Verify AIOps & Slack Connection:**
Run the `curl` test command to ensure your Slack webhook is active and you receive the "System Online" message.
3. **Establish Baseline Data:**
Execute the `normal_traffic.sh` script immediately to begin populating your graphs with healthy data.
4. **Stage the Incident:**
Open a new terminal window and type the command to run `simulate_incident.sh`, but **do not hit Enter yet**.

---

## The Demo Narrative (Script)

### Phase 1: The Baseline (The "Before")* 

**Show:** The Grafana Dashboard (Localhost:3001).
* **Say:**
> "Here is the system running in a healthy steady state. Notice our latency is stable (<100ms) and we have a 100% success rate on requests. This establishes our 'Golden Signals' baseline."

### Phase 2: The Incident (The "Action")* 
**Action:** Hit **Enter** on your staged terminal to run the incident script.
* **Say:**
> "I am now simulating a production incident—specifically a 'bad deployment' that introduces both traffic saturation and broken endpoints."

### Phase 3: The Detection (The "AIOps Reveal")* 
**Show:** The **Slack Alert** popping up or the **AIOps logs**.

* **Say:**
* > "Standard static thresholds often miss this, or alert too late. But look—our LSTM-based AIOps engine detected the anomaly immediately. It noticed the deviation from the learned baseline and fired this alert to Slack."

### Phase 4: The Diagnosis (The "Expertise")* 
**Show:** The **Latency Heatmap** panel.
* **Say:**
> "We can confirm the impact here. Average latency looks okay, but this Heatmap reveals a hidden band of users suffering 2-second delays. It’s not the database; it’s application saturation causing Event Loop lag."

---

## Architecture Talking Points* 
**Observability Pattern:** 
> "I'm using the Sidecar pattern here. Prometheus scrapes the Express app over the internal Docker bridge network."
* **Scalability:**
> "This mimics a production Kubernetes environment where we would use Sidecars or DaemonSets to scale data collection."
* **Why Event Loop Lag?**
> "In Node.js, CPU is a misleading metric. I track Event Loop Lag because it predicts 504 Timeouts before they happen."

---

## Technical Setup & Configuration Requirements

Ensure the following files are present and configured in your project root before the demo:

### 1. Chaos Scripts

Ensure these are in your `/scripts` folder and are executable (`chmod +x`).

* **Script A:** `normal_traffic.sh` (The Baseline) - *Generates continuous healthy traffic to the health and products endpoints.*
* **Script B:** `simulate_incident.sh` (The Chaos) - *Simulates a batch of 404 errors and heavy traffic saturation.*

### 2. Docker Compose Configuration* 
**File:** `docker-compose.yml`
* **Note:** Ensure Grafana is mapped to port **3001** (host) to avoid conflicts with the App on port 3000.
* **Note:** Ensure the `aiops` service environment variable `SLACK_WEBHOOK_URL` is set to your actual Slack webhook URL.

---

## Q&A "Consultant Checks" (Cheat Sheet)

| Question | Expert Answer |
| :--- | :--- |
| **"Why is there a gap in the data?"** | "Likely a missed scrape interval (default 15s) or a container restart. In prod, I'd use `absent()` alerts to catch this." |
| **"How do we secure this?"** | "For production, I'd place Grafana behind an OAuth proxy (like Google Auth) and enforce mTLS between Prometheus and targets." |
| **"Can we scale this globally?"** | "Prometheus is great for single clusters. For global scale, I would integrate **Thanos** or **Cortex** for long-term storage and federated querying." |
| **"Why use an LSTM model?"** | "Static thresholds are noisy. LSTMs learn seasonality—they know that high traffic on Monday morning is normal, but high traffic on Sunday night is an anomaly." |
