# Golden Platform Advanced Observability Stack

## Enterprise Observability Model

Golden Platform implements the three pillars of observability: **Logs**, **Metrics**, and **Traces**.

```
┌──────────────────────────────────────────────────────────┐
│ Golden Platform Observability Stack │
├──────────────────────────────────────────────────────────┤
│ │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ Traces │ │ Metrics │ │ Logs │ │
│ │ (OpenTelem) │ │ (Prometheus)│ │ (ELK/Loki) │ │
│ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ │
│ │ │ │ │
│ └────────────────┼────────────────┘ │
│ │ │
│ ┌───────────────┐ │
│ │ OpenTelemetry│ │
│ │ Collector │ │
│ └───────┬────────┘ │
│ │ │
│ ┌─────────────────┼─────────────────┐ │
│ │ │ │ │
│ ┌──────┐ ┌───────┐ ┌─────┐ │
│ │Jaeger │ │Grafana │ │PagerDuty │
│ │(Trace)│ │(Visual)│ │(Alerts) │
│ └───────┘ └────────┘ └───────┘ │
│ │
│ SLO/Error Budget Tracking │
│ ├─ 99.999% availability target │
│ ├─ 31 seconds downtime/year error budget │
│ ├─ Automatic alert on budget burn │
│ └─ Compliance dashboard │
│ │
└──────────────────────────────────────────────────────┘
```

---

## 1. OpenTelemetry Instrumentation

### Python Auto-Instrumentation

```python
# golden/observability/otel_setup.py
from opentelemetry import trace, metrics
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.kafka import KafkaInstrumentor
from fastapi import FastAPI

def setup_opentelemetry(app: FastAPI, service_name: str, environment: str):
    """
    Initialize OpenTelemetry for Golden Platform services
    Automatically instruments: HTTP, database, cache, messaging
    """
    
    # Resource identification
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "environment": environment,
        "deployment.environment": environment,
        "service.version": "2.0.0"
    })
    
    # ===== TRACING SETUP =====
    jaeger_exporter = JaegerExporter(
        agent_host_name="jaeger-collector.monitoring.svc.cluster.local",
        agent_port=6831,
    )
    
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )
    trace.set_tracer_provider(trace_provider)
    
    # ===== METRICS SETUP =====
    prometheus_reader = PrometheusMetricReader()
    metrics_provider = MeterProvider(
        resource=resource,
        metric_readers=[prometheus_reader]
    )
    metrics.set_meter_provider(metrics_provider)
    
    # ===== AUTO-INSTRUMENTATION =====
    # FastAPI HTTP instrumentation
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)
    
    # Database instrumentation
    SQLAlchemyInstrumentor().instrument()
    Psycopg2Instrumentor().instrument()
    
    # HTTP client instrumentation
    RequestsInstrumentor().instrument()
    
    # Kafka producer/consumer instrumentation
    KafkaInstrumentor().instrument()
    
    return trace_provider, metrics_provider

# Expose Prometheus metrics endpoint
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    "/metrics": make_wsgi_app()
})
```

### Custom Span Attributes

```python
# golden/observability/tracing.py
from opentelemetry import trace
from functools import wraps
from typing import Any, Callable

tracer = trace.get_tracer(__name__)

def traced_operation(operation_name: str):
    """Decorator to trace any function"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(operation_name) as span:
                # Add custom attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("operation.success", True)
                    return result
                except Exception as e:
                    span.set_attribute("operation.success", False)
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(operation_name) as span:
                span.set_attribute("function.name", func.__name__)
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("operation.success", True)
                    return result
                except Exception as e:
                    span.set_attribute("operation.success", False)
                    span.set_attribute("error.type", type(e).__name__)
                    raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

# Usage example
@traced_operation("fraud_detection.assess_transaction")
async def assess_transaction(transaction_id: str, amount: float):
    """Assess transaction for fraud - automatically traced"""
    # Spans include: function name, module, success/failure, latency
    ...
```

### Fintech-Specific Instrumentation

```python
# golden/fintech/observability.py
from opentelemetry import trace, metrics

class FinTechMetrics:
    def __init__(self):
        meter = metrics.get_meter(__name__)
        
        # Transaction metrics
        self.transaction_counter = meter.create_counter(
            "golden.transaction.processed",
            description="Total transactions processed",
            unit="1"
        )
        
        self.transaction_latency = meter.create_histogram(
            "golden.transaction.latency",
            description="Transaction processing latency",
            unit="ms"
        )
        
        self.fraud_score_distribution = meter.create_histogram(
            "golden.fraud.score",
            description="Fraud detection score distribution",
            unit="1"
        )
        
        self.fraud_accuracy = meter.create_gauge(
            "golden.fraud.accuracy",
            description="Fraud detection accuracy",
            unit="%"
        )
        
        # Transaction amount tracking (for aggregated analytics)
        self.transaction_volume = meter.create_counter(
            "golden.transaction.volume",
            description="Total transaction volume",
            unit="USD"
        )
    
    def record_transaction(self, amount: float, currency: str, 
                          fraud_score: float, success: bool, 
                          latency_ms: float):
        """Record transaction metrics"""
        self.transaction_counter.add(
            1,
            {"currency": currency, "success": success}
        )
        self.transaction_latency.record(latency_ms)
        self.fraud_score_distribution.record(fraud_score)
        self.transaction_volume.add(amount, {"currency": currency})
```

### Healthcare-Specific Instrumentation

```python
# golden/healthcare/observability.py
class HealthcareMetrics:
    def __init__(self):
        meter = metrics.get_meter(__name__)
        
        # Patient monitoring metrics
        self.vital_readings = meter.create_counter(
            "golden.patient.vital_readings",
            description="Vital sign readings recorded",
            unit="1"
        )
        
        self.alert_triggered = meter.create_counter(
            "golden.patient.alerts",
            description="Clinical alerts triggered",
            unit="1"
        )
        
        self.clinical_decision_latency = meter.create_histogram(
            "golden.clinical.decision_latency",
            description="Clinical decision support latency",
            unit="ms"
        )
        
        self.model_accuracy = meter.create_gauge(
            "golden.clinical.model_accuracy",
            description="Clinical prediction accuracy",
            unit="%"
        )
        
        # Patient attribution (HIPAA method: patient is SHA-256 hash)
        self.patients_monitored = meter.create_gauge(
            "golden.healthcare.patients_monitored",
            description="Number of patients being monitored",
            unit="1"
        )
    
    def record_vital_reading(self, patient_hash: str, vitals: dict, 
                           alerts: list):
        """Record vital sign reading with alerts"""
        self.vital_readings.add(1)
        for alert in alerts:
            self.alert_triggered.add(
                1,
                {"severity": alert["severity"], "type": alert["type"]}
            )
```

---

## 2. SLO & Error Budget Framework

### SLO Definition

```python
# golden/observability/slo.py
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

@dataclass
class ServiceLevelObjective:
    """Define SLOs for Golden Platform services"""
    
    service_name: str
    availability_percent: float # e.g., 99.999 for 99.999%
    latency_p99_ms: float
    latency_p95_ms: float
    error_budget_percent: float
    error_budget_period_days: int
    
    def calculate_error_budget_minutes(self) -> float:
        """Calculate error budget in minutes per period"""
        downtime_permitted = (100 - self.availability_percent) / 100
        total_minutes = self.error_budget_period_days * 24 * 60
        return total_minutes * downtime_permitted

# Define SLOs
FINTECH_TRANSACTION_SLO = ServiceLevelObjective(
    service_name="fintech-processor",
    availability_percent=99.999, # 31 seconds downtime/year
    latency_p99_ms=50, # <50ms to process transaction
    latency_p95_ms=30,
    error_budget_percent=0.001, # 0.001% of allowed errors
    error_budget_period_days=30 # Monthly SLO window
)

HEALTHCARE_CLINICAL_SLO = ServiceLevelObjective(
    service_name="clinical-decision",
    availability_percent=99.99, # 52 minutes downtime/year
    latency_p99_ms=100, # <100ms clinical decision
    latency_p95_ms=75,
    error_budget_percent=0.01,
    error_budget_period_days=30
)

API_GATEWAY_SLO = ServiceLevelObjective(
    service_name="api-gateway",
    availability_percent=99.99,
    latency_p99_ms=200,
    latency_p95_ms=150,
    error_budget_percent=0.01,
    error_budget_period_days=30
)

# Calculate error budgets
print(f"FinTech error budget: {FINTECH_TRANSACTION_SLO.calculate_error_budget_minutes():.2f} minutes/month")
# Output: FinTech error budget: 0.43 minutes/month (≈26 seconds)
```

### Error Budget Tracking

```python
# golden/observability/error_budget.py
from prometheus_client import Gauge, Counter, CollectorRegistry
from datetime import datetime, timedelta

class ErrorBudgetTracker:
    def __init__(self, slo: ServiceLevelObjective):
        self.slo = slo
        self.period_start = datetime.utcnow()
        self.errors = 0
        self.total_requests = 0
        
        # Prometheus metrics
        self.budget_remaining = Gauge(
            f"{slo.service_name}_error_budget_remaining_percent",
            "Remaining error budget percentage"
        )
        
        self.budget_burn_rate = Gauge(
            f"{slo.service_name}_error_budget_burn_rate",
            "Error budget burn rate (percent/minute)"
        )
        
        self.period_elapsed = Gauge(
            f"{slo.service_name}_slo_period_elapsed_percent",
            "SLO period elapsed percentage"
        )
    
    def record_request(self, success: bool):
        """Record request and update error budget"""
        self.total_requests += 1
        if not success:
            self.errors += 1
        
        self._update_metrics()
    
    def _update_metrics(self):
        """Update error budget metrics"""
        elapsed_minutes = (datetime.utcnow() - self.period_start).total_seconds() / 60
        period_minutes = self.slo.error_budget_period_days * 24 * 60
        
        # Current error rate
        if self.total_requests > 0:
            current_error_rate = self.errors / self.total_requests
        else:
            current_error_rate = 0
        
        # Allowed error rate
        allowed_error_rate = (100 - self.slo.availability_percent) / 100
        
        # Error budget consumed
        budget_consumed = min(current_error_rate / allowed_error_rate, 1.0)
        budget_remaining = max(0, 1.0 - budget_consumed)
        
        # Burn rate (percentage per minute)
        if elapsed_minutes > 0:
            burn_rate = (budget_consumed * 100) / elapsed_minutes
        else:
            burn_rate = 0
        
        # Update metrics
        self.budget_remaining.set(budget_remaining * 100)
        self.budget_burn_rate.set(burn_rate)
        self.period_elapsed.set(min(elapsed_minutes / period_minutes * 100, 100))
    
    def is_budget_critical(self) -> bool:
        """Check if error budget is running critically low"""
        elapsed_minutes = (datetime.utcnow() - self.period_start).total_seconds() / 60
        period_minutes = self.slo.error_budget_period_days * 24 * 60
        minutes_remaining = period_minutes - elapsed_minutes
        
        # Get current burn rate
        current_error_rate = self.errors / self.total_requests if self.total_requests > 0 else 0
        allowed_error_rate = (100 - self.slo.availability_percent) / 100
        burn_rate = current_error_rate / allowed_error_rate if allowed_error_rate > 0 else 0
        
        # Calculate if we'll exceed budget before period ends
        budget_required = burn_rate * minutes_remaining
        return budget_required > 1.0 # True if we'll exceed budget
```

### Alert Rules

```yaml
# prometheus-rules.yaml
groups:
- name: golden-slo-alerts
  interval: 30s
  rules:
  
  # Alert: Error budget burn rate too high
  - alert: HighErrorBudgetBurnRate
    expr: |
      (
        increase(golden_transaction_errors[5m]) / increase(golden_transaction_total[5m])
      ) / (1 - (99.999 / 100)) > 10 # 10x normal burn rate
    for: 5m
    labels:
      severity: critical
      slo_name: fintech_transaction
    annotations:
      summary: "{{ $labels.service }} error budget burning at {{ $value }}x normal rate"
      description: |
        Service {{ $labels.service }} is burning error budget at 10x expected rate.
        Current error rate: {{ $value }}%
        SLO allows: 0.001%
        Action: Investigate increased error rate immediately.

  # Alert: Error budget exhausted
  - alert: ErrorBudgetExhausted
    expr: |
      (
        increase(golden_transaction_errors[30d]) / increase(golden_transaction_total[30d])
      ) > (1 - (99.999 / 100)) # Exceeded threshold
    for: 1m
    labels:
      severity: critical
      slo_name: fintech_transaction
    annotations:
      summary: "{{ $labels.service }} has exhausted monthly error budget"
      description: |
        Service {{ $labels.service }} has exceeded its monthly error budget.
        Stop shipping new features.
        Focus on reliability improvements.

  # Alert: Latency SLO violation
  - alert: LatencySLOViolation
    expr: |
      histogram_quantile(0.99, golden_transaction_latency_ms) > 50 # P99 > 50ms SLO
    for: 5m
    labels:
      severity: warning
      slo_name: fintech_transaction
    annotations:
      summary: "{{ $labels.service }} P99 latency exceeds SLO"
      description: |
        Current P99 latency: {{ $value }}ms
        SLO threshold: 50ms
        Action: Investigate performance regression.
```

---

## 3. Monitoring Dashboards

### Grafana Dashboard Configuration

```json
{
  "dashboard": {
    "title": "Golden Platform - Fintech Transaction Engine",
    "panels": [
      {
        "title": "Transaction Throughput",
        "targets": [
          {
            "expr": "increase(golden_transaction_processed[5m])"
          }
        ],
        "yaxis": {
          "label": "Transactions/min"
        }
      },
      {
        "title": "Latency (P95, P99, P99.9)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, golden_transaction_latency_ms)"
          },
          {
            "expr": "histogram_quantile(0.99, golden_transaction_latency_ms)"
          },
          {
            "expr": "histogram_quantile(0.999, golden_transaction_latency_ms)"
          }
        ]
      },
      {
        "title": "Fraud Detection Accuracy",
        "targets": [
          {
            "expr": "golden_fraud_accuracy"
          }
        ],
        "thresholds": [95]
      },
      {
        "title": "Error Budget Remaining (%)",
        "targets": [
          {
            "expr": "golden_fintech_transaction_error_budget_remaining_percent"
          }
        ],
        "alertThreshold": 20
      },
      {
        "title": "Service Dependencies (Trace View)",
        "type": "trace",
        "datasource": "Jaeger"
      }
    ]
  }
}
```

### Healthcare Dashboard

```json
{
  "dashboard": {
    "title": "Golden Platform - Healthcare Patient Monitoring",
    "panels": [
      {
        "title": "Patients Monitored",
        "expression": "golden_healthcare_patients_monitored"
      },
      {
        "title": "Vital Readings/Hour",
        "expression": "increase(golden_patient_vital_readings[1h])"
      },
      {
        "title": "Critical Alerts Triggered",
        "expression": "increase(golden_patient_alerts{severity='CRITICAL'}[1h])"
      },
      {
        "title": "Clinical Decision Latency (P99)",
        "expression": "histogram_quantile(0.99, golden_clinical_decision_latency_ms)"
      },
      {
        "title": "Model Accuracy by Condition",
        "expression": "golden_clinical_model_accuracy"
      }
    ]
  }
}
```

---

## 4. Advanced Observability Features

### Distributed Tracing

```python
# golden/observability/tracing_example.py
@traced_operation("process_transaction_full_trace")
async def process_transaction(transaction_id: str):
    """
    Traces the full journey of a transaction through the system.
    
    Trace includes:
    - Transaction validation
    - Fraud detection (external service)
    - Settlement processing
    - Compliance check
    - Final settlement
    """
    
    tracer = trace.get_tracer(__name__)
    
    # Span 1: Retrieve transaction details
    with tracer.start_as_current_span("retrieve_transaction") as span:
        span.set_attribute("transaction.id", transaction_id)
        transaction = await db.get_transaction(transaction_id)
        span.add_event("transaction_retrieved", {
            "amount": transaction.amount,
            "currency": transaction.currency
        })
    
    # Span 2: Validate transaction
    with tracer.start_as_current_span("validate_transaction") as span:
        is_valid = await validator.validate(transaction)
        span.set_attribute("validation.result", is_valid)
    
    # Span 3: Fraud detection (might call external service)
    with tracer.start_as_current_span("fraud_assessment") as span:
        fraud_result = await fraud_detector.assess(transaction)
        span.set_attribute("fraud.score", fraud_result.score)
        span.set_attribute("fraud.decision", fraud_result.decision)
    
    # Span 4: Settlement
    with tracer.start_as_current_span("process_settlement") as span:
        settlement = await settlement_engine.settle(transaction)
        span.set_attribute("settlement.id", settlement.id)
        span.set_attribute("settlement.time_ms", settlement.processing_time)
    
    # Trace shows parent-child relationships:
    # process_transaction_full_trace
    # ├─ retrieve_transaction (10ms)
    # ├─ validate_transaction (5ms)
    # ├─ fraud_assessment (40ms) [external service call visible]
    # └─ process_settlement (20ms)
    # Total: 75ms
```

### Metrics Correlation

```python
# golden/observability/correlation.py
class MetricsCorrelation:
    """
    Correlate metrics across different dimensions
    for root cause analysis
    """
    
    async def find_anomalies(self):
        """
        Find correlations between:
        - Increased error rate
        - Increased latency
        - Increased CPU on specific pods
        - Increased memory usage
        - Network latency
        """
        results = {
            "error_spike_causes": [],
            "latency_spike_causes": [],
            "resource_anomalies": []
        }
        
        # Check for common root causes
        error_rate = await self.query_metric("error_rate")
        cpu_usage = await self.query_metric("pod_cpu_usage")
        memory_usage = await self.query_metric("pod_memory_usage")
        network_latency = await self.query_metric("network_latency")
        db_connection_pool = await self.query_metric("db_connection_pool_usage")
        
        # Correlation logic
        if error_rate > 0.001 and db_connection_pool > 0.9:
            results["error_spike_causes"].append({
                "cause": "Database connection pool exhaustion",
                "confidence": 0.95,
                "remediation": "Increase pool size or implement circuit breaker"
            })
        
        if error_rate > 0.001 and cpu_usage > 0.85:
            results["error_spike_causes"].append({
                "cause": "CPU saturation on processor pods",
                "confidence": 0.87,
                "remediation": "Scale horizontally or optimize code"
            })
        
        return results
```

---

## 5. Observability-Driven Development

### Observability Checklist for New Features

```markdown
# Observability Checklist

Before merging any new feature, ensure:

## Metrics
- [ ] All business-critical operations have counter metrics
- [ ] All latency-sensitive operations have histogram metrics
- [ ] Service dependencies are instrumented
- [ ] Error conditions are labeled and tracked
- [ ] Resource usage is monitored (CPU, memory, connections)

## Logging
- [ ] INFO logs for business events (transactions, decisions)
- [ ] ERROR logs with full context (request ID, tenant, user)
- [ ] Structured logging with JSON format
- [ ] Sensitive data is redacted (passwords, SSNs, authentication tokens)
- [ ] Log retention meets compliance requirements

## Tracing
- [ ] All request entry points create root spans
- [ ] Service-to-service calls are traced
- [ ] Database queries include transaction ID
- [ ] External API calls are traced
- [ ] Trace sampling configured appropriately (100% for critical paths)

## Alerts
- [ ] SLO alerts configured (error budget, latency)
- [ ] Business alerts configured (fraud detected, critical patient alert)
- [ ] On-call escalation paths defined
- [ ] Runbooks created for common alerts
- [ ] Alert fatigue analyzed (>5 alerts/week needs review)

## Dashboards
- [ ] Business metrics dashboard created
- [ ] Technical dashboard for debugging
- [ ] Team drill-down dashboard
- [ ] Alert dashboard (currently firing alerts)
```

---

## Infrastructure & Deployment

### Docker Compose (Development)

```yaml
# observability/docker-compose.yml
version: '3.8'
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686" # UI
      - "6831:6831/udp" # OTLP receiver
    environment:
      COLLECTOR_OTLP_ENABLED: "true"

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    ports:
      - "3000:3000"
    depends_on:
      - prometheus

  otel-collector:
    image: otel/opentelemetry-collector:latest
    volumes:
      - ./otel-collector-config.yaml:/etc/otel/config.yaml
    ports:
      - "4317:4317" # OTLP gRPC
      - "4318:4318" # OTLP HTTP
    command: ["--config", "/etc/otel/config.yaml"]
```

---

## References

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [SLO Best Practices](https://sre.google/sre-book/service-level-objectives/)
- [Jaeger Distributed Tracing](https://www.jaegertracing.io/)

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
