# Observability Dashboards Playbook

## When to Use
- New service onboarding.
- Post-incident validation.
- Quarterly operational readiness reviews.

## Required Dashboards
1. **Ingestion Health**
   - Telemetry rate (events/sec)
   - Drop/parse error rate
   - End-to-end ingestion latency
2. **Kafka Backbone**
   - Consumer lag by group
   - Broker disk usage
   - Under-replicated partitions
3. **Storage & Query**
   - Write latency p95/p99
   - Query latency p95/p99
   - Indexing backlog
4. **System Health**
   - CPU, memory, and saturation
   - Pod restarts and crash loops
   - Node pressure events

## Steps
1. Create a dashboard folder named `AIOps-Operations`.
2. Add panels for each required metric above.
3. Set alert thresholds:
   - Ingestion latency p99 > 5s (warning), > 10s (critical)
   - Kafka lag > 10k messages for 10m
   - Storage write latency p99 > 2s
4. Validate dashboards during a controlled load test.

## Evidence
- Export the dashboard JSON and store it in change records.
- Capture screenshots for audit-ready evidence.

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
