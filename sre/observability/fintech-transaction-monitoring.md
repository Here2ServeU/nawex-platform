# Fintech Transaction Monitoring - Observability Setup

## Overview

This document describes the observability configuration for the **Fintech** vertical of the Express-Reliability AIOps Platform. It extends the existing [OpenTelemetry](/sre/observability/opentelemetry-tracing-setup.md) and [Datadog](/sre/observability/datadog-apm-setup.md) setup with fintech-specific metrics, dashboards, and alerts.

## Fintech Metrics Collection

### Transaction Engine Metrics
| Metric | Type | Description |
| --- | --- | --- |
| `fintech.transactions.total` | Counter | Total transactions processed |
| `fintech.transactions.approved` | Counter | Approved transactions |
| `fintech.transactions.blocked` | Counter | Blocked (fraud) transactions |
| `fintech.transactions.latency_ms` | Histogram | Transaction processing latency |
| `fintech.transactions.error_rate` | Gauge | Rolling error rate |
| `fintech.transactions.throughput_tps` | Gauge | Transactions per second |

### Fraud Detector Metrics
| Metric | Type | Description |
| --- | --- | --- |
| `fintech.fraud.scored_total` | Counter | Total transactions scored |
| `fintech.fraud.flagged_total` | Counter | Transactions flagged as fraud |
| `fintech.fraud.scoring_latency_ms` | Histogram | ML inference latency |
| `fintech.fraud.model_precision` | Gauge | Current model precision |
| `fintech.fraud.model_recall` | Gauge | Current model recall |
| `fintech.fraud.false_positive_rate` | Gauge | False positive rate |

### Payment Gateway Metrics
| Metric | Type | Description |
| --- | --- | --- |
| `fintech.gateway.processed_total` | Counter | Payments processed |
| `fintech.gateway.latency_ms` | Histogram | Gateway processing latency |
| `fintech.gateway.error_rate` | Gauge | Gateway error rate |
| `fintech.gateway.settlement_batches` | Counter | Settlement batches triggered |

## SLO Definitions

### Payment Processing SLO
- **Objective**: 99.99% of transactions processed successfully within 100ms
- **Error Budget**: 0.01% (~4.3 minutes/month)
- **Burn Rate Alert**: >2% budget consumption in 1 hour

### Fraud Detection SLO
- **Objective**: 100% of transactions scored within 50ms
- **Precision Target**: >95%
- **False Positive Rate**: <0.1%

### Settlement SLO
- **Objective**: All settlement batches complete within clearing window (120 min)
- **Zero-Loss Target**: No transactions lost during settlement processing

## Grafana Dashboard Configuration

### Fintech Overview Dashboard
```json
{
  "dashboard": {
    "title": "Fintech Operations Center",
    "panels": [
      {"title": "Transaction Volume (TPS)", "type": "graph"},
      {"title": "Fraud Detection Rate", "type": "stat"},
      {"title": "Payment Gateway Latency P99", "type": "gauge"},
      {"title": "Settlement Progress", "type": "bargauge"},
      {"title": "Error Budget Remaining", "type": "stat"},
      {"title": "Active Fraud Alerts", "type": "table"}
    ]
  }
}
```

## Alert Rules

### Critical Alerts (PagerDuty escalation)
1. **Payment SLO Breach**: Transaction error rate > 0.01% for 5 minutes
2. **Fraud Spike**: Fraud detection rate exceeds 5x baseline
3. **Settlement Delay**: Batch estimated completion exceeds clearing window
4. **Gateway Failover**: Primary payment gateway health check failing

### Warning Alerts (Slack notification)
1. **Latency Degradation**: P99 transaction latency > 80ms
2. **Model Drift**: Fraud model precision drops below 93%
3. **Volume Anomaly**: Transaction volume deviates >3σ from baseline
