# Data Pipeline Observability Playbook

## Purpose
Establish comprehensive observability for telemetry ingestion pipelines—covering Kafka throughput, consumer lag, Splunk indexing, and storage system health.

## When to Use
- Establishing baseline metrics for a new deployment.
- Debugging high-latency or data-loss incidents.
- Quarterly operational readiness reviews.

## Key Metrics & Thresholds

### 1. Kafka Producer Health
| Metric | p95 Threshold | p99 Threshold | Alert Action |
| :--- | :--- | :--- | :--- |
| **Produce Latency** | < 100ms | < 500ms | Page SRE if exceeded for 5 min |
| **Record Send Rate** | > 1K events/sec | > 500 events/sec | Warn, check for throttling |
| **Compression Ratio** | > 1.5x | > 2x | Monitor, baseline expected value |
| **Buffer Exhaustion** | < 95% | < 90% | Alert, scale producer instances |

### 2. Kafka Consumer Health
| Metric | Threshold | Alert Action |
| :--- | :--- | :--- |
| **Consumer Group Lag** | < 10K messages | Page SRE if lag grows for > 5 min |
| **Consumer Fetch Latency** | < 500ms p95 | Investigate broker disk/network |
| **Rebalance Duration** | < 30 sec | Tune session timeout if > 60 sec |
| **Member Count** | Expected count ± 0 | Alert on unexpected joins/leaves |

### 3. Splunk Indexing
| Metric | Threshold | Alert Action |
| :--- | :--- | :--- |
| **HEC Input Rate** | Baseline ± 20% | Page on-call if > 30% deviation |
| **Indexing Latency** | < 2 sec field extraction | Investigate transforms config |
| **Queue Fill Rate** | < 80% | Increase queue depth or scale indexers |
| **Parse Error Rate** | < 1% of total events | Investigate schema changes, validate parsing rules |

### 4. Storage System Health
| Metric | Threshold | Alert Action |
| :--- | :--- | :--- |
| **Write Latency** | < 2 sec p99 | Investigate disk I/O, check replication |
| **Disk Usage** | < 80% | Trigger retention cleanup jobs |
| **Replication Lag** | < 1 sec | Alert on failed replicas, trigger failover |
| **Query Latency** | < 5 sec p95 | Tune indexes, consider caching layer |

## Implementation (Grafana Dashboard)
1. **Create Data Source Connections:**
   - Prometheus (Kafka JMX exporter metrics)
   - Splunk (REST API queries for indexing metrics)
   - CloudWatch (EC2/RDS storage metrics)

2. **Kafka Producer Panel:**
   ```
   rate(kafka_producer_record_send_latency_avg[5m])
   kafka_producer_record_send_total
   ```

3. **Kafka Consumer Lag Panel:**
   ```
   sum(kafka_consumergroup_lag) by (consumergroup, topic)
   ```

4. **Splunk HEC Throughput Panel:**
   ```
   splunk_hec_events_processed_total
   splunk_hec_input_queue_fill_ratio
   ```

5. **Storage Write Latency Panel:**
   ```
   histogram_quantile(0.99, rate(storage_write_latency_seconds_bucket[5m]))
   ```

## Splunk Configuration
Add to `props.conf` on the Splunk forwarder:
```ini
[kafka:// | kafka-zookeeper consumers]
TRANSFORMS = kafka_parser
KV_MODE = auto

[kafka_parser]
REGEX = ^(?<timestamp>\d+-\d+-\d+T\d+:\d+:\d+\.\d+Z)\s+(?<level>\w+)\s+(?<message>.*)$
FORMAT = timestamp::$1 level::$2 message::$3
```

## Validation Checklist
- [ ] Dashboard loads without errors.
- [ ] Metrics are non-zero for active pipelines.
- [ ] Alerts fire during a synthetic load test.
- [ ] Consumer lag returns to baseline after load test ends.
- [ ] Splunk can query all indexed fields.
- [ ] Historical data is retained per compliance policy.

## Runbook Links
- [Kafka Healthcheck](./kafka_healthcheck.md)
- [Queue Drain Kafka](./queue_drain_kafka.md)
- [Observability Dashboards](./observability_dashboards.md)

---

*Copyright (c) 2026 Nawex Platform (NAWEX). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
