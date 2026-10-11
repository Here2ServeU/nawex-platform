# 08: PSD2 & Open Banking Compliance

## Executive Summary

This document outlines the platform's compliance with the **Payment Services Directive 2 (PSD2)** and Open Banking standards. The [Golden Platform](/) implements Strong Customer Authentication (SCA), secure API access for Third-Party Providers (TPPs), and real-time transaction monitoring to meet EU regulatory requirements for payment service providers.

## PSD2 Technical Requirements Mapping

| PSD2 Requirement | Platform Control Implementation | Evidence Location |
| --- | --- | --- |
| **Strong Customer Authentication (SCA)** | Multi-factor authentication enforced at the API Gateway (Kong) for all payment initiation and account access requests. Dynamic linking binds each authentication to transaction amount and payee. | [`/helm/kong-gateway`](/deploy/helm/kong-gateway), [`/sre/security/mfa-policy-setup.sh`](/ops/sre/security/mfa-policy-setup.sh) |
| **Secure Communication (Art. 35)** | All TPP API communications use mTLS 1.3 with eIDAS-qualified certificates; Istio Service Mesh enforces zero-trust networking. | [`/helm/service-mesh`](/deploy/helm/service-mesh) |
| **Transaction Risk Analysis (TRA)** | Real-time fraud scoring via [LSTM/TCN models](/src/golden/ai/) enables exemptions from SCA for low-risk transactions (under €500) based on fraud rate thresholds. | [`/ai/pipelines`](/src/golden/ai/pipelines) |
| **API Access for TPPs (Art. 36)** | Dedicated Open Banking API endpoints exposed via Kong Gateway with OAuth 2.0 / FAPI (Financial-grade API) security profiles. | [`/helm/kong-gateway`](/deploy/helm/kong-gateway) |
| **Incident Reporting (Art. 96)** | Automated incident detection and reporting pipeline; major payment incidents are flagged within 4 hours per regulatory requirement. | [`/ops/playbooks`](/ops/runbooks/playbooks), [`/sre/observability`](/ops/sre/observability) |
| **Operational Resilience** | Active-Active Multi-Cloud architecture ensures payment services meet 99.999% availability targets required by competent authorities. | [`/docs/architecture/05-active-active-resilience.md`](/docs/architecture/05-active-active-resilience.md) |

## Open Banking API Security

The platform implements Financial-grade API (FAPI) security profiles for Open Banking:

* **FAPI 2.0 Compliance**: OAuth 2.0 with PKCE, PAR (Pushed Authorization Requests), and JARM (JWT Secured Authorization Response Mode) enforced at the API Gateway.
* **Consent Management**: Granular consent tracking with cryptographic proof of customer authorization; consent records are immutable and auditable.
* **Rate Limiting & Throttling**: Per-TPP rate limits enforced at Kong Gateway to prevent abuse while ensuring fair access per regulatory requirements.
* **Certificate-Based Identity**: TPP identification via eIDAS certificates (QWAC/QSealC) validated at the network edge.

## Transaction Monitoring & Fraud Prevention

The [Predictive Reliability Framework](/docs/architecture/04-predictive-reliability-framework.md) powers continuous transaction monitoring:

* **Real-Time Risk Scoring**: Every transaction receives a fraud probability score from the AI engine, enabling dynamic SCA exemptions under PSD2's Transaction Risk Analysis provisions.
* **Velocity Checks**: ML models detect unusual transaction velocity patterns (e.g., rapid successive payments, geographic impossibilities) and trigger step-up authentication.
* **Automated Blocking**: Transactions exceeding fraud thresholds (P > 0.90) are automatically blocked, and the customer is notified within 30 seconds per SCA requirements.

## Data Protection (GDPR Integration)

PSD2 compliance is tightly coupled with GDPR requirements:

* **Data Minimization**: Only transaction data necessary for payment processing and fraud prevention is collected and processed.
* **Right to Erasure**: Customer payment data can be purged on request, with cryptographic proof of deletion maintained for audit purposes.
* **Cross-Border Transfers**: Financial data residency enforced via Kubernetes node affinity and namespace-level network policies, ensuring EU payment data stays within EEA boundaries.

---

### Regulatory Alignment

This mapping positions the platform as a compliant foundation for Account Information Service Providers (AISPs), Payment Initiation Service Providers (PISPs), and Card-Based Payment Instrument Issuers (CBPIIs) operating under PSD2 across the European Economic Area.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
