# 05: Post-Quantum Cryptography (PQC) Readiness Plan

> **Status: readiness plan, not an implemented feature.** The repository does not ship ML-KEM (Kyber),
> ML-DSA (Dilithium) or SLH-DSA code, PQC certificates or PQC-signed audit logs. Today the audit trail
> is SHA-256 hash-chained ([`src/golden/security/audit.py`](../../src/golden/security/audit.py)) and model
> artifacts are checked against a SHA-256 manifest (`golden security manifest`). This page describes how a
> deploying organisation would migrate to PQC. See [CLAIMS.md](../CLAIMS.md).

## Executive Overview

Large-scale quantum computers would break today's public-key algorithms (RSA, ECDH, ECDSA). Data with a long confidentiality life — patient records, financial records, audit evidence — is exposed to "harvest now, decrypt later" collection today. In August 2024 NIST published the first PQC standards:

| Standard | Algorithm | Use |
| --- | --- | --- |
| **FIPS 203** | ML-KEM (from CRYSTALS-Kyber) | Key encapsulation (TLS key exchange) |
| **FIPS 204** | ML-DSA (from CRYSTALS-Dilithium) | Digital signatures |
| **FIPS 205** | SLH-DSA (from SPHINCS+) | Hash-based signatures (conservative backup) |

Symmetric cryptography (AES-256-GCM) and SHA-256/384 are considered adequate with current key sizes; the migration work is on key exchange and signatures.

## Phase 1 — Cryptographic inventory

Build a crypto bill of materials before changing anything:

| Area in this repo | What to record |
| --- | --- |
| TLS at ingress and mesh ([`deploy/helm/service-mesh`](../../deploy/helm/service-mesh), [`deploy/helm/kong-gateway`](../../deploy/helm/kong-gateway)) | Protocol versions, key-exchange groups, certificate algorithms, issuing CA |
| Terraform state and secrets ([`deploy/terraform`](../../deploy/terraform)) | KMS key specs (symmetric vs asymmetric), who holds asymmetric keys |
| Audit and model integrity ([`src/golden/security`](../../src/golden/security)) | Hash algorithms; any signatures (none today) |
| CI/CD and images ([`.github/workflows`](../../.github/workflows)) | Image/commit signing approach (if adopted), OIDC token algorithms |
| Cloud provider services | Provider PQC support per service (load balancers, KMS, managed TLS) |

Output: a register of every asymmetric algorithm in use, the data it protects, and that data's required confidentiality lifetime.

## Phase 2 — Prioritise

Rank by (data lifetime) × (exposure). In this platform the first candidates would be:

1. External TLS for PHI and payment APIs (harvest-now-decrypt-later risk).
2. Service-to-service mTLS in the mesh.
3. Long-lived signatures: audit-log anchors, model-artifact manifests, release signing.

## Phase 3 — Hybrid migration

* **Key exchange:** enable hybrid X25519 + ML-KEM-768 groups where the TLS stack and load balancers support them (several cloud load balancers and recent OpenSSL/BoringSSL builds do). Hybrid keeps classical security if an ML-KEM implementation flaw is found.
* **Signatures:** add ML-DSA alongside existing signatures for audit anchors and artifact manifests once the signing toolchain supports it; keep verifying both during transition.
* **Crypto agility:** keep algorithm choice in configuration, not code, so a second migration is a config change.

## Phase 4 — Validate and monitor

* Handshake success and latency before/after enabling hybrid groups (record p95 per endpoint).
* Interoperability tests with partners, payment processors and EHR systems.
* A recurring check that no new non-agile asymmetric crypto enters the inventory.

## Compliance Alignment

PQC is not yet a stated requirement of HIPAA, HDS, PCI DSS or SOX. This plan supports their long-term data-protection expectations and aligns with NIST's PQC guidance. See [HIPAA mapping](01-hipaa-compliance-mapping.md), [HDS](02-data-privacy-hds.md), [PCI DSS](06-pci-dss-compliance-mapping.md) and [SOX](07-sox-compliance-mapping.md).

### Fintech considerations

* **Transaction signing:** evaluate ML-DSA for long-lived non-repudiation records once HSM vendors support it.
* **Payment channels:** hybrid ML-KEM key exchange depends on processor and scheme support; track it in the inventory.
* **HSMs:** confirm the vendor's FIPS 203/204 roadmap before committing to timelines.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
