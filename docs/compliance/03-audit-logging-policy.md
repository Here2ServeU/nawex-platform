# 03: Audit Logging & Monitoring Policy

> **Mapping, not certification.** This document maps platform controls to the audit requirements of HIPAA, HDS, PCI DSS and SOX. The platform has not been audited or certified against it. Rows describe the target control design; only items that link to code or config in this repository are implemented here, and the rest are requirements for the deploying organisation. See [CLAIMS.md](../CLAIMS.md).

## Executive Overview

This document defines the technical standards for capturing, protecting, and reviewing audit logs within the [Golden Platform](https://github.com/Here2ServeU/nawex-platform). Per [HIPAA §164.312(b)](01-hipaa-compliance-mapping.md), the platform implements hardware, software, and procedural mechanisms that record and examine activity in information systems that contain or use electronic protected health information (ePHI).

## Scope of Logging

The platform captures granular telemetry across the entire [multi-cloud stack](../architecture/03-infrastructure-topology.md):

| Log Category | Source Component | Data Captured |
| --- | --- | --- |
| **System Access** | [IAM / RBAC](../../deploy/terraform) | User ID, Timestamp, Source IP, Success/Failure status. |
| **AI Decisioning** | [Predictive Brain](../../src/golden/ai) | Risk probability scores (), input telemetry features, and triggered actions. |
| **Infrastructure** | [GitOps (ArgoCD)](../../deploy/gitops) | Commit SHA, Author, and diffs of all environmental changes. |
| **Clinical Safety** | [Robotics Edge](../../src/golden/robotics) | Kinematic anomaly flags and agentic safety mediation events. |
| **Financial Transactions** | [Transaction Engine](/src/golden/ai/pipelines/detect_fraud.py) | Transaction IDs, amounts, fraud scores, payment gateway responses, settlement events. |
| **Regulatory Compliance** | [Compliance Engine](/docs/compliance) | PCI-DSS scope validation, SOX control testing, PSD2 SCA decisions, GLBA access audits. |

## Immutability & Protection

To prevent log tampering and satisfy [HDS standards](02-data-privacy-hds.md), the following protections are enforced:

* **Write-Once-Read-Many (WORM)** *(deployment requirement)*: Logs should be streamed to encrypted, object-locked buckets in [GCP and AWS](../architecture/03-infrastructure-topology.md). Object-lock buckets for logs are not provisioned by `deploy/terraform` today.
* **Cryptographic Hashing**: Every audit entry carries the SHA-256 of its predecessor, so editing or deleting an entry breaks the chain ([`src/golden/security/audit.py`](../../src/golden/security/audit.py); `golden security status` reports chain validity).
* **Separation of Duties**: The [SRE team](../../ops/sre) cannot modify or delete logs; only the dedicated Security Auditor role has read-only access.

## Predictive Audit Review

Utilizing the [Predictive Reliability Framework](../architecture/04-predictive-reliability-framework.md), the platform performs continuous, automated log analysis:

* **Anomaly Detection**: The [AI Brain](../../src/golden/ai) flags unusual administrative patterns that may indicate credential compromise.
* **Automated Alerting**: High-risk security events raise Prometheus alerts and can trigger governed resource isolation. (Cross-cloud [active-active failover](../architecture/05-active-active-resilience.md) is a design target.)

## Retention Requirements

Logs are retained according to the following schedule to meet legal mandates:

* **Active Logs**: 90 days in high-performance [TSDB](../architecture/02-data-flow-diagrams.md).
* **Archive Logs**: 7 years in cold storage (GCS/S3) for HIPAA/HDS/SOX/GLBA regulatory look-backs.
* **Financial Transaction Logs**: 5 years minimum per PCI-DSS Requirement 10.7; 7 years for SOX-relevant systems.

---

### Strategy for your Portfolio

This policy proves you understand that **Observability is a Compliance Requirement**. By linking your [AI models](../../src/golden/ai) to the auditing process, you demonstrate a "Security-First" engineering mindset.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
