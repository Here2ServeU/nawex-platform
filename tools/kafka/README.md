# Kafka Ops Tooling

## Local (Docker Compose)
- Bootstrap server: `kafka:9092`
- Container name: `kafka_broker`

## Kubernetes
- Bootstrap server: `kafka.apps.svc.cluster.local:9092`

## Healthcheck
```bash
tools/kafka/kafka-healthcheck.sh
```

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
