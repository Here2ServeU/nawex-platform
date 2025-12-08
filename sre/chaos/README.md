# Chaos Engineering & Resilience Suite

This directory contains the **Resilience Validation Framework** used to proactively test system stability. These scripts are executed as part of the CI/CD pipeline and scheduled maintenance windows to enforce "Anti-Fragile" architecture.

### 1. `pod-kill-test.sh`
* **Core Functionality:** Randomly terminates running Kubernetes pods within targeted namespaces using `kubectl delete pod` with randomized grace periods.
* **SRE Challenge Solved:** **Statelessness Verification.** Validates that microservices effectively handle sudden termination without data loss or user session interruption, ensuring true horizontal scalability.
* **Operational Impact:** Confirms that `replicaSets` and HPA (Horizontal Pod Autoscalers) react correctly to unexpected process failures, maintaining service availability.

### 2. `node-failure-test.sh`
* **Core Functionality:** Simulates underlying infrastructure failure by cordoning and draining nodes, or forcibly terminating worker node instances via cloud provider CLIs (AWS CLI/gcloud).
* **SRE Challenge Solved:** **Infrastructure Redundancy.** Tests the cluster’s ability to reschedule workloads to healthy nodes without service downtime.
* **Operational Impact:** Verifies that **PodDisruptionBudgets (PDBs)** are correctly configured and that capacity planning allows for the loss of a compute node during peak loads.

### 3. `network-latency-injection.sh`
* **Core Functionality:** Uses traffic control tools (like `tc` or service mesh fault injection) to introduce artificial latency and packet loss between microservices.
* **SRE Challenge Solved:** **Timeout & Retry Logic.** Exposes hidden dependencies and "cascading failure" risks where a slow downstream service causes upstream request queues to fill up.
* **Operational Impact:** Validates that circuit breakers and timeout thresholds are correctly tuned, preventing a minor network blip from becoming a system-wide outage.

### 4. `dependency-failure-simulation.sh`
* **Core Functionality:** Blocks access to critical external dependencies (e.g., DNS, databases, or third-party APIs) via network policies or mock responses.
* **SRE Challenge Solved:** **Graceful Degradation.** Ensures the application can still serve core functionality (or fail with a user-friendly error) when non-essential dependencies go dark.
* **Operational Impact:** Enforces "Zero Trust" resilience, ensuring that a failure in a 3rd-party API does not crash the entire platform.

### 5. `region-failover-test.sh`
* **Core Functionality:** Simulates a complete regional outage by routing traffic away from the primary region to a secondary standby region (DR).
* **SRE Challenge Solved:** **Disaster Recovery (DR) Readiness.** Validates the RTO (Recovery Time Objective) and RPO (Recovery Point Objective) of the global architecture.
* **Operational Impact:** proves the effectiveness of multi-region active-active or active-passive setups, ensuring business continuity during catastrophic cloud provider outages.

---
**Summary:** This suite implements **Continuous Verification**, moving beyond "hoping" systems are resilient to mathematically proving they can withstand production turbulence.
