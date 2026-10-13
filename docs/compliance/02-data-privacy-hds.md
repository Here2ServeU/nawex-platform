# 02: Data Privacy & HDS Compliance (Hébergement de Données de Santé)

> **Mapping, not certification.** This document maps platform controls to the French HDS framework. The platform has not been audited or certified against it. Rows describe the target control design; only items that link to code or config in this repository are implemented here, and the rest are requirements for the deploying organisation. See [CLAIMS.md](../CLAIMS.md).

## Executive Overview

This document outlines the privacy controls implemented to meet the **HDS (Hébergement de Données de Santé)** certification requirements for the [Golden Platform](https://github.com/Here2ServeU/nawex-platform). These standards ensure that personal health data stored or processed within our [multi-cloud infrastructure](../architecture/03-infrastructure-topology.md) remains secure, private, and under the control of the patient/provider.

## HDS Technical Requirements Mapping

As per the French Public Health Code, HDS certification covers six hosting activities. The platform's design maps to them as follows (certification applies to the hosting provider, not to this template):

| Activity | Technical Implementation | Platform Evidence |
| --- | --- | --- |
| **PaaS / IaaS Security** | Provisioning of secure virtual infrastructure across [EKS, AKS, and GKE](../architecture/03-infrastructure-topology.md). | [`/terraform`](https://www.google.com/search?q=%5B../../deploy)) |
| **Application Hosting** | Secure container orchestration with automated [GitOps](../../deploy/gitops) deployment pipelines. | [`/gitops`](https://www.google.com/search?q=%5B../../deploy)) |
| **Backup & DR** | Multi-region continuity design ([Active-Active Resilience](../architecture/05-active-active-resilience.md), not implemented); near-zero RPO is a target. | [`/docs/compliance/04`](https://www.google.com/search?q=%5B.)) |
| **Data Encryption** | Mandatory Encryption-at-Rest (AES-256) and Encryption-in-Transit (TLS 1.3) across all cloud providers. | [`/docs/architecture/02`](https://www.google.com/search?q=%5B../architecture)) |

## Data Residency & Sovereignty

To satisfy European GDPR and French HDS requirements, the platform enforces strict data residency rules:

* **Region Pinning**: Critical clinical telemetry is pinned to specific EU regions (e.g., `eu-west-3` for France) to ensure data never leaves the required legal jurisdiction.
* **Cross-Border Controls**: The [GCP Vertex AI training loop](../architecture/04-predictive-reliability-framework.md) utilizes anonymized data sets to ensure no PHI/PII is exposed during model optimization.

## Privacy by Design in AIOps

Our [Predictive Reliability Framework](../architecture/04-predictive-reliability-framework.md) includes built-in privacy safeguards:

* **Data Minimization**: Only essential kinematic telemetry required for safety inference is processed by the [AI Brain](../../src/golden/ai).
* **Automated Anonymization**: All telemetry streams are scrubbed of identifiable metadata at the [Robotics Edge](../../src/golden/robotics) before ingestion into the cloud control plane.

---

### Strategy for your Portfolio

Adding **HDS** to your documentation highlights your ability to navigate complex international regulations. This is a massive differentiator for leadership roles in global healthcare tech.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
