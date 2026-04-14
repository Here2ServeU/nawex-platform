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

### 6. `payment-gateway-failure.sh` (Fintech)
* **Core Functionality:** Injects latency and errors into the payment gateway to validate automated failover, transaction integrity preservation, and fraud detection resilience.
* **SRE Challenge Solved:** **Payment Downtime.** Validates that payment processing can survive gateway degradation without losing in-flight transactions.
* **Compliance:** PCI-DSS Req 11 (regular security testing), SOX business continuity validation.
* **Operational Impact:** Proves that the platform can maintain payment SLOs during infrastructure failures, preserving transaction integrity via Kafka buffering.

### 7. `transaction-fraud-spike.sh` (Fintech)
* **Core Functionality:** Simulates a coordinated fraud attack by injecting high-risk transactions to validate the fraud detection pipeline, automated blocking, and incident response procedures.
* **SRE Challenge Solved:** **Fraud Response Readiness.** Ensures the fraud detection model, automated blocking rules, and ops team notification all function under attack conditions.
* **Compliance:** PCI-DSS Req 11 (penetration testing), PSD2 Art. 96 (incident response validation).
* **Operational Impact:** Validates the entire fraud response chain from ML scoring through automated remediation to human escalation.

### 8. `ehr-gateway-failure.sh` (Healthcare)
* **Core Functionality:** Injects latency and errors into the FHIR/HL7 patient data gateway to validate automated failover, clinical data integrity preservation, and EHR query resilience.
* **SRE Challenge Solved:** **Clinical Data Availability.** Validates that EHR processing can survive gateway degradation without losing in-flight clinical queries.
* **Compliance:** HIPAA §164.308 (contingency testing), FDA 21 CFR Part 11 (system reliability validation).
* **Operational Impact:** Proves that the platform can maintain clinical SLOs during infrastructure failures, preserving HIPAA audit trail continuity via Kafka buffering.

### 9. `phi-breach-simulation.sh` (Healthcare)
* **Core Functionality:** Simulates anomalous PHI access patterns (cross-department, after-hours, bulk export) to validate breach detection, automated session lockout, and HIPAA incident response procedures.
* **SRE Challenge Solved:** **PHI Breach Response.** Ensures the PHI anomaly detection model, automated user lockout, and compliance team notification all function under breach conditions.
* **Compliance:** HIPAA §164.308 (security incident procedures), HITECH (breach notification validation).
* **Operational Impact:** Validates the entire breach response chain from ML-based access anomaly detection through automated lockout to HIPAA Privacy Officer escalation.

---
**Summary:** This suite implements **Continuous Verification**, moving beyond "hoping" systems are resilient to mathematically proving they can withstand production turbulence.

---

*Copyright (c) 2026 Nawex Platform (NAWEX). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
