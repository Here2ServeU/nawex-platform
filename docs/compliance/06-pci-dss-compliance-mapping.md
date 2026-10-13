# 06: PCI-DSS Compliance & Security Mapping

> **Mapping, not certification.** This document maps platform controls to the PCI DSS v4.0. The platform has not been audited or certified against it. Rows describe the target control design; only items that link to code or config in this repository are implemented here, and the rest are requirements for the deploying organisation. See [CLAIMS.md](../CLAIMS.md).

## Executive Summary

This document provides a traceability matrix between the **Golden Platform** technical controls and the **Payment Card Industry Data Security Standard (PCI-DSS v4.0)**. The platform is designed to handle cardholder data (CHD), payment transactions, and financial telemetry streams by enforcing encryption, zero-trust networking, tokenization, and automated auditability.

## PCI-DSS Requirements Mapping

| PCI-DSS Requirement | Platform Control Implementation | Evidence Location |
| --- | --- | --- |
| **Req 1: Network Security Controls** | Kubernetes Network Policies, Istio Service Mesh mTLS, and Kong API Gateway enforce micro-segmentation of the Cardholder Data Environment (CDE). | [`/helm/service-mesh`](/deploy/helm/service-mesh), [`/helm/kong-gateway`](/deploy/helm/kong-gateway) |
| **Req 2: Secure Configurations** | Immutable container images scanned by Trivy; CIS Kubernetes Benchmark enforcement via OPA/Gatekeeper policies. | [`/scripts/trivy-scan.sh`](/scripts/tools/trivy-scan.sh), [`/gitops/policies`](/deploy/gitops/policies) |
| **Req 3: Protect Stored Account Data** | Tokenization of PAN (Primary Account Number) at ingestion; AES-256-GCM encryption-at-rest across all cloud providers. *(Design; tokenization is not implemented in this repo.)* | [`/docs/compliance/05-quantum-safe-encryption.md`](/docs/compliance/05-quantum-safe-encryption.md) (crypto inventory) |
| **Req 4: Protect Data in Transit** | Mandatory **mTLS 1.3** for all service-to-service communication; TLS 1.3 for external API endpoints via Kong Gateway. | [`/docs/architecture/02-data-flow-diagrams.md`](/docs/architecture/02-data-flow-diagrams.md) |
| **Req 5: Malware Protection** | Image vulnerability scanning with Trivy in CI. Runtime scanning (Falco) and provenance verification (Sigstore/Cosign) are recommended, not configured here. | [`/sre/security`](/ops/sre/security) |
| **Req 6: Secure Development** | SAST/DAST integrated into CI/CD pipeline; dependency scanning via Snyk and Trivy. | [`/scripts/demo-devsecops.sh`](/scripts/tools/demo-devsecops.sh) |
| **Req 7: Restrict Access** | RBAC-enforced access to Kubernetes clusters, payment processing namespaces, and AI inference engines using OIDC/SCIM providers. | [`/terraform`](/deploy/terraform), [`/sre/security`](/ops/sre/security) |
| **Req 8: Identify Users & Auth** | MFA enforcement, SSO integration (Okta/Azure AD), SCIM-based provisioning with time-bound access tokens. | [`/sre/security/mfa-policy-setup.sh`](/ops/sre/security/mfa-policy-setup.sh) |
| **Req 9: Physical Access** | Inherited from the cloud provider (AWS, Azure, GCP and OCI publish SOC 2 Type II and PCI DSS attestations; verify current reports) with dedicated VPCs. | [`/terraform`](/deploy/terraform) |
| **Req 10: Log & Monitor** | Tamper-evident (hash-chained) audit logging; WORM storage is a deployment requirement; anomaly detection on access patterns. | [`/docs/compliance/03-audit-logging-policy.md`](/docs/compliance/03-audit-logging-policy.md) |
| **Req 11: Security Testing** | Penetration testing is an organisational process (not provided here); chaos scripts are available to exercise failure modes. | [`/sre/chaos`](/ops/sre/chaos) |
| **Req 12: Organizational Policies** | Documented incident response plan, DR procedures, and security awareness training requirements. | [`/ops/playbooks`](/ops/runbooks/playbooks), [`/docs/compliance/04-disaster-recovery-plan.md`](/docs/compliance/04-disaster-recovery-plan.md) |

## AI-Driven PCI Compliance Monitoring

The platform leverages the [Predictive Reliability Framework](/docs/architecture/04-predictive-reliability-framework.md) for continuous PCI compliance validation:

* **Transaction Anomaly Detection**: The [LSTM/TCN models](/src/golden/ai/) monitor transaction velocity, geographic patterns, and amount distributions to identify potential fraud or data exfiltration in real-time.
* **Governed Isolation**: If a fraud score threshold is breached (P > 0.85, illustrative), the [Remediation Engine](/src/golden/ai/remediation/remediation_engine.py) can propose isolating the payment service; execution is subject to the `ActionGovernor` (approval in `supervised` mode). IP blocking and key rotation are design items.
* **Continuous Scope Validation** *(design)*: Network traffic analysis to detect scope creep—unauthorized systems communicating with the CDE.

## Tokenization Architecture

To minimize PCI scope, the target design is tokenization-first (not implemented in this repository):

* **Point-of-Entry Tokenization**: PANs are tokenized at the API Gateway (Kong) before entering the processing pipeline, ensuring raw cardholder data never touches application containers.
* **Token Vault**: A dedicated, encrypted token vault (isolated namespace with network policies) manages the mapping between tokens and original PANs.
* **Detokenization Controls**: Only the settlement service, running in a hardened CDE namespace, can detokenize for processor submission—requiring multi-factor authorization for any configuration changes.

## Data Residency for Financial Data

The [Multi-Cloud Topology](/docs/architecture/03-infrastructure-topology.md) enforces jurisdiction-specific data residency for financial data:

* **US Transactions**: Processed and stored in `us-east-1` / `us-west-2` regions.
* **EU/EEA Transactions**: Pinned to `eu-west-1` / `eu-central-1` for GDPR and PSD2 compliance.
* **APAC Transactions**: Routed to `ap-southeast-1` for regional regulatory requirements.

---

### Compliance Certification Path

This mapping is a starting point for a PCI DSS assessment. **PCI-DSS Level 1 Service Provider** status would require the operating organisation to implement the design items above and pass a QSA assessment (ROC/AOC); this template alone does not confer it.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
