# Kafka Healthcheck Playbook

## When to Use
- Post-deployment validation.
- During ingestion latency incidents.
- Before schema migrations.

## Steps
1. Run the healthcheck tool:
```bash
tools/kafka/kafka-healthcheck.sh
```
2. Validate broker visibility and topic list.
3. Check consumer lag in dashboards.
4. If lag is high, follow [queue_drain_kafka.md](./queue_drain_kafka.md).

## Expected Output
- Broker metadata is returned.
- Topic list is non-empty for active pipelines.
- No connection errors or timeouts.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
