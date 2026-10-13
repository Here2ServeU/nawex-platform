# 01: HIPAA Compliance & Security Mapping

> **Mapping, not certification.** This document maps platform controls to the HIPAA Security Rule. The platform has not been audited or certified against it. Rows describe the target control design; only items that link to code or config in this repository are implemented here, and the rest are requirements for the deploying organisation. See [CLAIMS.md](../CLAIMS.md).

## Executive Summary

This document provides a traceability matrix between the **Golden Platform** technical controls and the **HIPAA Security Rule** (45 CFR § 164.312). The platform is designed to handle Protected Health Information (PHI) within clinical robotics and telemetry streams by enforcing encryption, zero-trust networking, and automated auditability.

## Technical Safeguards Mapping

| HIPAA Standard | Platform Control Implementation | Evidence Location |
| --- | --- | --- |
| **Access Control** (164.312.a.1) | RBAC-enforced access to Kubernetes clusters and AI inference engines using OIDC providers. | [`/terraform/iam`](https://www.google.com/search?q=%5B../../deploy)) |
| **Audit Controls** (164.312.b) | Immutable logging of all [GitOps](../../deploy/gitops) changes and AI-driven failover events in a centralized TSDB. | [`/docs/architecture/05`](https://www.google.com/search?q=%5B../architecture)) |
| **Integrity** (164.312.c.1) | Digital signing of [container images](../../scripts) and checksum verification of robotics telemetry packets. | [`/robotics/safety`](https://www.google.com/search?q=%5B../../src/golden)) |
| **Transmission Security** (164.312.e.1) | Mandatory **mTLS 1.3** for all service-to-service communication via Istio Service Mesh across multi-cloud regions. | [`/docs/architecture/02`](https://www.google.com/search?q=%5B../architecture)) |

## AI-Driven Compliance Monitoring

Unlike traditional platforms, this system leverages the [Predictive Reliability Framework](../architecture/04-predictive-reliability-framework.md) to detect security anomalies:

* **Predictive Anomaly Detection**: The [LSTM/TCN models](../../src/golden/ai) monitor telemetry access patterns to identify potential unauthorized PHI exfiltration or "man-in-the-middle" attacks at the robotics edge.
* **Governed Remediation**: If a security threshold is breached, the remediation engine can propose isolating the compromised node or rotating keys via GitOps; execution is gated by the `ActionGovernor` (autonomy mode, approvals, kill switch).

## Data Residency & Sovereignty

To support international healthcare standards (including **HDS** for French data), the [Multi-Cloud Topology](../architecture/03-infrastructure-topology.md) ensures that patient data remains within geographically defined boundaries (e.g., `us-east-1` for US patients, `eu-west-1` for EU patients) through Kubernetes taints and affinity rules.

---

### Strategy for your Portfolio

This document signals to a **CISO or CTO** that you understand the liability and regulatory overhead of healthcare tech. It moves the repository from a "coding project" towards a product that a covered entity could take through its own HIPAA risk analysis. It does not make the product HIPAA-compliant on its own.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
