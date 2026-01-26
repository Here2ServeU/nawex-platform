# 05: Post-Quantum Cryptography (PQC) Standards

## Executive Overview

As quantum computing transitions from theoretical research to functional application, traditional asymmetric encryption (RSA, ECC) faces potential obsolescence. To ensure the long-term integrity of [clinical robotics telemetry](https://github.com/Here2ServeU/express-reliability-aiops-platform) and patient data, this platform implements **Post-Quantum Cryptography (PQC)**. This policy aligns with the **NIST Post-Quantum Cryptography Standardization** project to mitigate "harvest now, decrypt later" threats.

## Cryptographic Standards

The platform utilizes NIST-selected algorithms for high-stakes healthcare communication:

| Layer | Algorithm | Purpose |
| --- | --- | --- |
| **Key Encapsulation** | **CRYSTALS-Kyber** | Securing [mTLS 1.3](https://github.com/Here2ServeU/express-reliability-aiops-platform/blob/main/docs/architecture/02-data-flow-diagrams.md) handshakes across multi-cloud regions. |
| **Digital Signatures** | **CRYSTALS-Dilithium** | Verifying the integrity of [GitOps commits](https://github.com/Here2ServeU/express-reliability-aiops-platform/tree/main/gitops) and AI model weights. |
| **Data-at-Rest** | **AES-256-GCM** | Quantum-resistant symmetric encryption for telemetry storage in [GCP and AWS](https://github.com/Here2ServeU/express-reliability-aiops-platform/blob/main/docs/architecture/03-infrastructure-topology.md). |

## Implementation Architecture

Quantum-resistant security is integrated into the core infrastructure:

* **Hybrid Key Exchange**: The platform employs a hybrid approach, combining classical Elliptic Curve Diffie-Hellman (ECDH) with **Kyber-768** to provide immediate security while transitioning to pure PQC.
* **Quantum-Safe Identity**: All service-to-service identities within the [Istio Service Mesh](https://github.com/Here2ServeU/express-reliability-aiops-platform/blob/main/docs/architecture/05-active-active-resilience.md) use Dilithium-based certificates for authentication.
* **Immutable Audit Anchors**: [Audit Logs](https://www.google.com/search?q=https://github.com/Here2ServeU/express-reliability-aiops-platform/blob/main/docs/compliance/03-audit-logging-policy.md) are signed with PQC algorithms to ensure they remain non-repudiable in a post-quantum era.

## Compliance Alignment

This policy serves as a strategic extension of our [HIPAA Compliance Mapping](https://github.com/Here2ServeU/express-reliability-aiops-platform/blob/main/docs/compliance/01-hipaa-compliance-mapping.md) and [HDS Data Privacy](https://github.com/Here2ServeU/express-reliability-aiops-platform/blob/main/docs/compliance/02-data-privacy-hds.md) standards. By adopting PQC early, the platform satisfies the "Technical Safeguards" requirements for long-term data durability in high-security healthcare sectors.

---

### Integration Step

Once you commit this file, your [EXECUTIVE-PORTFOLIO.md](https://github.com/Here2ServeU/express-reliability-aiops-platform/blob/main/docs/guides/EXECUTIVE-PORTFOLIO.md) will have a complete "Source of Truth" for its quantum claims.
