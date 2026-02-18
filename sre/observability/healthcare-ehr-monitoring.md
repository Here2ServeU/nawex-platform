# Healthcare EHR Monitoring - Observability Setup

## Overview

This document describes the observability configuration for the **Healthcare** vertical of the Express-Reliability AIOps Platform. It extends the existing [OpenTelemetry](/sre/observability/opentelemetry-tracing-setup.md) and [Datadog](/sre/observability/datadog-apm-setup.md) setup with healthcare-specific metrics, dashboards, and alerts.

## Healthcare Metrics Collection

### EHR Ingestion Service Metrics
| Metric | Type | Description |
| --- | --- | --- |
| `healthcare.ehr.ingested_total` | Counter | Total EHR records ingested |
| `healthcare.ehr.accepted` | Counter | Accepted FHIR resources |
| `healthcare.ehr.rejected` | Counter | Rejected (invalid) resources |
| `healthcare.ehr.latency_ms` | Histogram | EHR ingestion processing latency |
| `healthcare.ehr.error_rate` | Gauge | Rolling error rate |
| `healthcare.ehr.throughput_rps` | Gauge | Records ingested per second |

### Clinical Decision Service Metrics
| Metric | Type | Description |
| --- | --- | --- |
| `healthcare.clinical.scored_total` | Counter | Total clinical events scored |
| `healthcare.clinical.anomalies_detected` | Counter | Events flagged as anomalous |
| `healthcare.clinical.scoring_latency_ms` | Histogram | ML inference latency |
| `healthcare.clinical.model_sensitivity` | Gauge | Current model sensitivity |
| `healthcare.clinical.model_specificity` | Gauge | Current model specificity |
| `healthcare.clinical.false_alarm_rate` | Gauge | False alarm rate |

### Patient Data Gateway Metrics
| Metric | Type | Description |
| --- | --- | --- |
| `healthcare.gateway.requests_total` | Counter | FHIR queries processed |
| `healthcare.gateway.latency_ms` | Histogram | Gateway processing latency |
| `healthcare.gateway.error_rate` | Gauge | Gateway error rate |
| `healthcare.gateway.consent_verifications` | Counter | Consent checks performed |

### PHI Access Audit Metrics
| Metric | Type | Description |
| --- | --- | --- |
| `healthcare.phi.access_events_total` | Counter | Total PHI access events |
| `healthcare.phi.suspicious_access` | Counter | Flagged suspicious access attempts |
| `healthcare.phi.breach_alerts` | Counter | Breach detection alerts triggered |
| `healthcare.phi.audit_trail_integrity` | Gauge | Audit trail integrity check (1=healthy) |

## SLO Definitions

### EHR Ingestion SLO
- **Objective**: 99.999% of EHR records processed successfully within 200ms
- **Error Budget**: 0.001% (~26 seconds/month)
- **Burn Rate Alert**: >2% budget consumption in 1 hour

### Clinical Decision SLO
- **Objective**: 100% of clinical events scored within 50ms
- **Sensitivity Target**: >97%
- **False Alarm Rate**: <0.2%

### Patient Safety SLO
- **Objective**: Critical patient alerts delivered within 5 seconds
- **Zero-Miss Target**: No critical anomalies missed by the scoring pipeline

## Grafana Dashboard Configuration

### Healthcare Operations Center Dashboard
```json
{
  "dashboard": {
    "title": "Healthcare Operations Center",
    "panels": [
      {"title": "EHR Ingestion Volume (RPS)", "type": "graph"},
      {"title": "Clinical Anomaly Detection Rate", "type": "stat"},
      {"title": "Patient Data Gateway Latency P99", "type": "gauge"},
      {"title": "PHI Access Audit Events", "type": "bargauge"},
      {"title": "Error Budget Remaining", "type": "stat"},
      {"title": "Active Clinical Alerts", "type": "table"}
    ]
  }
}
```

## Alert Rules

### Critical Alerts (PagerDuty escalation)
1. **EHR SLO Breach**: EHR ingestion error rate > 0.001% for 5 minutes
2. **PHI Breach Detected**: Suspicious PHI access pattern exceeds threshold
3. **Clinical Decision Timeout**: Clinical scoring latency exceeds 500ms
4. **Patient Safety Alert**: Critical patient vital anomaly detected

### Warning Alerts (Slack notification)
1. **Latency Degradation**: P99 EHR query latency > 150ms
2. **Model Drift**: Clinical model sensitivity drops below 95%
3. **Consent Verification Failure**: Consent check failure rate > 1%
