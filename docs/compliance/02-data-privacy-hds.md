# 02: Data Privacy & HDS Compliance (Hébergement de Données de Santé)

## Executive Overview

This document outlines the privacy controls implemented to meet the **HDS (Hébergement de Données de Santé)** certification requirements for the [Naweji Reliability Platform](https://github.com/Here2ServeU/Naweji-Reliability-Platform). These standards ensure that personal health data stored or processed within our [multi-cloud infrastructure](https://github.com/Here2ServeU/Naweji-Reliability-Platform/blob/main/docs/architecture/03-infrastructure-topology.md) remains secure, private, and under the control of the patient/provider.

## HDS Technical Requirements Mapping

As per the French Public Health Code, the platform satisfies the six main activities of HDS certification:

| Activity | Technical Implementation | Platform Evidence |
| --- | --- | --- |
| **PaaS / IaaS Security** | Provisioning of secure virtual infrastructure across [EKS, AKS, and GKE](https://github.com/Here2ServeU/Naweji-Reliability-Platform/blob/main/docs/architecture/03-infrastructure-topology.md). | [`/terraform`](https://www.google.com/search?q=%5Bhttps://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/terraform%5D(https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/terraform)) |
| **Application Hosting** | Secure container orchestration with automated [GitOps](https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/gitops) deployment pipelines. | [`/gitops`](https://www.google.com/search?q=%5Bhttps://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/gitops%5D(https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/gitops)) |
| **Backup & DR** | Multi-region, multi-cloud [Active-Active Resilience](https://github.com/Here2ServeU/Naweji-Reliability-Platform/blob/main/docs/architecture/05-active-active-resilience.md) with near-zero RPO. | [`/docs/compliance/04`](https://www.google.com/search?q=%5Bhttps://github.com/Here2ServeU/Naweji-Reliability-Platform/blob/main/docs/compliance/04-disaster-recovery-plan.md%5D(https://github.com/Here2ServeU/Naweji-Reliability-Platform/blob/main/docs/compliance/04-disaster-recovery-plan.md)) |
| **Data Encryption** | Mandatory Encryption-at-Rest (AES-256) and Encryption-in-Transit (TLS 1.3) across all cloud providers. | [`/docs/architecture/02`](https://www.google.com/search?q=%5Bhttps://github.com/Here2ServeU/Naweji-Reliability-Platform/blob/main/docs/architecture/02-data-flow-diagrams.md%5D(https://github.com/Here2ServeU/Naweji-Reliability-Platform/blob/main/docs/architecture/02-data-flow-diagrams.md)) |

## Data Residency & Sovereignty

To satisfy European GDPR and French HDS requirements, the platform enforces strict data residency rules:

* **Region Pinning**: Critical clinical telemetry is pinned to specific EU regions (e.g., `eu-west-3` for France) to ensure data never leaves the required legal jurisdiction.
* **Cross-Border Controls**: The [GCP Vertex AI training loop](https://github.com/Here2ServeU/Naweji-Reliability-Platform/blob/main/docs/architecture/04-predictive-reliability-framework.md) utilizes anonymized data sets to ensure no PHI/PII is exposed during model optimization.

## Privacy by Design in AIOps

Our [Predictive Reliability Framework](https://github.com/Here2ServeU/Naweji-Reliability-Platform/blob/main/docs/architecture/04-predictive-reliability-framework.md) includes built-in privacy safeguards:

* **Data Minimization**: Only essential kinematic telemetry required for safety inference is processed by the [AI Brain](https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/ai).
* **Automated Anonymization**: All telemetry streams are scrubbed of identifiable metadata at the [Robotics Edge](https://github.com/Here2ServeU/Naweji-Reliability-Platform/tree/main/robotics) before ingestion into the cloud control plane.

---

### Strategy for your Portfolio

Adding **HDS** to your documentation highlights your ability to navigate complex international regulations. This is a massive differentiator for leadership roles in global healthcare tech.

