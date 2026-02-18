# Healthcare Reliability: SLO Definitions & Error Budgets

## Overview

This document defines the **Service Level Objectives (SLOs)** for the Healthcare vertical, extending the platform's [reliability framework](/sre/reliability/reliability-architecture.md) with clinical-operations-specific targets. These SLOs are designed to satisfy HIPAA availability requirements, FDA system reliability mandates, and patient safety objectives.

## Tier-1 SLOs (Patient-Safety-Critical)

### EHR Ingestion
| SLI | Target | Error Budget (30d) | Measurement |
| --- | --- | --- | --- |
| Availability | 99.999% | 26 seconds | Percentage of successful EHR ingestion API responses (2xx) |
| Latency (p50) | ≤ 25ms | N/A | Median EHR record processing time |
| Latency (p99) | ≤ 200ms | 0.5% breaches allowed | 99th percentile EHR processing time |
| Data Integrity | 100% | 0 tolerance | Zero lost or corrupted clinical records |

### Clinical Decision Support
| SLI | Target | Error Budget (30d) | Measurement |
| --- | --- | --- | --- |
| Availability | 99.999% | 26 seconds | Clinical scoring endpoint uptime |
| Scoring Latency | ≤ 50ms (p99) | 0.05% breaches | ML inference time per clinical event |
| Sensitivity | ≥ 97% | Monitored weekly | Ratio of true positives to total actual anomalies |
| False Alarm Rate | ≤ 0.2% | Monitored daily | Normal events incorrectly flagged as anomalous |

### Patient Data Gateway
| SLI | Target | Error Budget (30d) | Measurement |
| --- | --- | --- | --- |
| Availability | 99.999% | 26 seconds | Gateway health check success rate |
| Failover Time | ≤ 3 seconds | N/A | Time to complete FHIR gateway failover |
| Error Rate | ≤ 0.001% | Per-gateway measurement | FHIR query processing error rate |

## Tier-2 SLOs (Operational)

### PHI Access Monitoring
| SLI | Target | Error Budget | Measurement |
| --- | --- | --- | --- |
| Audit Completeness | 100% | 0 tolerance | All PHI access events logged with full context |
| Breach Detection | ≤ 60 seconds | N/A | Time from anomalous access to alert generation |

### Clinical Data Exchange
| SLI | Target | Measurement |
| --- | --- | --- |
| Interoperability | 99.9% FHIR R4 compliance | Validation against FHIR R4 spec |
| Consent Verification | 100% pre-access | Every data request checked against consent records |

## Error Budget Policies

### Budget Healthy (>50% remaining)
- Feature development proceeds normally
- Standard deployment cadence
- Routine chaos engineering drills (HIPAA contingency testing)

### Budget Warning (25-50% remaining)
- Enhanced monitoring activated
- Deployments require SRE and clinical safety review
- Daily error budget review meetings

### Budget Critical (<25% remaining)
- Feature freeze for affected services
- All engineering effort redirected to reliability
- Post-incident reviews required for each budget-consuming event
- HIPAA Security Officer notified

### Budget Exhausted (0%)
- All non-critical changes halted
- Emergency reliability sprint initiated
- Executive and HIPAA Privacy Officer escalation
- Regulatory incident assessment per HITECH requirements

## Burn Rate Alerting

| Window | Burn Rate | Alert Severity | Action |
| --- | --- | --- | --- |
| 5 minutes | 14.4x | **Critical** | Page on-call, auto-scale, prepare failover, notify clinical ops |
| 30 minutes | 6x | **High** | Page on-call, investigate root cause |
| 6 hours | 1x | **Warning** | Slack alert, schedule investigation |
| 3 days | 1x | **Info** | Daily review, trend analysis |

## Compliance Mapping

| SLO | Regulatory Requirement |
| --- | --- |
| EHR Availability 99.999% | HIPAA §164.308 Contingency Plan |
| Clinical Decision ≤50ms | FDA 21 CFR Part 11 System Reliability |
| PHI Audit 100% completeness | HIPAA §164.312(b) Audit Controls |
| Zero data loss | HIPAA §164.312(c) Integrity Controls |
| Failover ≤3s | HIPAA DR Plan / SOC 2 Availability |
| Consent 100% pre-access | HIPAA §164.508 Authorization |
