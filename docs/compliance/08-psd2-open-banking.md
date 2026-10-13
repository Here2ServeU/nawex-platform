# 08: PSD2 & Open Banking Compliance

> **Mapping, not certification.** This document maps platform controls to the PSD2 / Open Banking requirements. The platform has not been audited or certified against it. Rows describe the target control design; only items that link to code or config in this repository are implemented here, and the rest are requirements for the deploying organisation. See [CLAIMS.md](../CLAIMS.md).

## Executive Summary

This document maps the platform against the **Payment Services Directive 2 (PSD2)** and Open Banking standards. The target design covers Strong Customer Authentication (SCA), secure API access for Third-Party Providers (TPPs), and real-time transaction monitoring for payment service providers. Of these, real-time transaction risk scoring is implemented (`fraud-detector`); SCA, FAPI and eIDAS handling are design items for the Kong gateway.

## PSD2 Technical Requirements Mapping

| PSD2 Requirement | Platform Control Implementation | Evidence Location |
| --- | --- | --- |
| **Strong Customer Authentication (SCA)** | Multi-factor authentication enforced at the API Gateway (Kong) for all payment initiation and account access requests. Dynamic linking binds each authentication to transaction amount and payee. | [`/helm/kong-gateway`](/deploy/helm/kong-gateway), [`/sre/security/mfa-policy-setup.sh`](/ops/sre/security/mfa-policy-setup.sh) |
| **Secure Communication (Art. 35)** | All TPP API communications use mTLS 1.3 with eIDAS-qualified certificates; Istio Service Mesh enforces zero-trust networking. | [`/helm/service-mesh`](/deploy/helm/service-mesh) |
| **Transaction Risk Analysis (TRA)** | Real-time explainable 5-signal fraud scoring ([`detect_fraud.py`](/src/golden/ai/pipelines/detect_fraud.py)) can support exemptions from SCA for low-risk transactions (under €500) based on fraud rate thresholds. | [`/ai/pipelines`](/src/golden/ai/pipelines) |
| **API Access for TPPs (Art. 36)** | Dedicated Open Banking API endpoints exposed via Kong Gateway with OAuth 2.0 / FAPI (Financial-grade API) security profiles. | [`/helm/kong-gateway`](/deploy/helm/kong-gateway) |
| **Incident Reporting (Art. 96)** | Automated incident detection and reporting pipeline; the 4-hour initial-report window is a process requirement (not automated here). | [`/ops/playbooks`](/ops/runbooks/playbooks), [`/sre/observability`](/ops/sre/observability) |
| **Operational Resilience** | 99.9% API availability SLO objective in Prometheus; an Active-Active Multi-Cloud design (not implemented) for higher targets. | [`/docs/architecture/05-active-active-resilience.md`](/docs/architecture/05-active-active-resilience.md) |

## Open Banking API Security

Target Financial-grade API (FAPI) security profile for Open Banking (design; not configured in this repository):

* **FAPI 2.0 profile**: OAuth 2.0 with PKCE, PAR (Pushed Authorization Requests), and JARM (JWT Secured Authorization Response Mode) enforced at the API Gateway.
* **Consent Management**: Granular consent tracking with cryptographic proof of customer authorization; consent records are immutable and auditable.
* **Rate Limiting & Throttling**: Per-TPP rate limits enforced at Kong Gateway to prevent abuse while ensuring fair access per regulatory requirements.
* **Certificate-Based Identity**: TPP identification via eIDAS certificates (QWAC/QSealC) validated at the network edge.

## Transaction Monitoring & Fraud Prevention

The [Predictive Reliability Framework](/docs/architecture/04-predictive-reliability-framework.md) powers continuous transaction monitoring:

* **Real-Time Risk Scoring**: Every transaction receives a fraud probability score from the AI engine, enabling dynamic SCA exemptions under PSD2's Transaction Risk Analysis provisions.
* **Velocity Checks**: ML models detect unusual transaction velocity patterns (e.g., rapid successive payments, geographic impossibilities) and trigger step-up authentication.
* **Automated Blocking**: Transactions above the fraud threshold (`FRAUD_THRESHOLD`, default 0.75) are flagged `is_fraud`; blocking and customer notification are integration responsibilities of the payment flow.

## Data Protection (GDPR Integration)

PSD2 compliance is tightly coupled with GDPR requirements:

* **Data Minimization**: Only transaction data necessary for payment processing and fraud prevention is collected and processed.
* **Right to Erasure**: Customer payment data can be purged on request, with cryptographic proof of deletion maintained for audit purposes.
* **Cross-Border Transfers**: Financial data residency enforced via Kubernetes node affinity and namespace-level network policies, ensuring EU payment data stays within EEA boundaries.

---

### Regulatory Alignment

This mapping is a starting point for Account Information Service Providers (AISPs), Payment Initiation Service Providers (PISPs), and Card-Based Payment Instrument Issuers (CBPIIs) operating under PSD2 across the European Economic Area.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
