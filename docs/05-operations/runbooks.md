# Operational Playbooks for Golden Platform

This directory contains tactical, step-by-step procedures (**Playbooks**) designed to standardize routine and emergency operational tasks across the Golden Platform microservices and Backstage IDP infrastructure. Adherence to these playbooks minimizes operational risk and ensures predictable outcomes.

## Available Playbooks

| Playbook File | Operational Task | Applies To |
| :--- | :--- | :--- |
| [db_failover_postgres.md](../../ops/runbooks/playbooks/db_failover_postgres.md) | Executing a controlled failover from the primary PostgreSQL instance to a synchronous replica. | Backstage IDP, Core Microservices |
| [cache_warmup_redis.md](../../ops/runbooks/playbooks/cache_warmup_redis.md) | Standardized procedure for pre-filling critical application caches after deployment or service restart. | Microservices using Redis |
| [queue_drain_kafka.md](../../ops/runbooks/playbooks/queue_drain_kafka.md) | Safely stopping Kafka consumers during maintenance or deployment to prevent data loss or duplicate processing. | Async Microservices (Kafka) |
| [kafka_healthcheck.md](../../ops/runbooks/playbooks/kafka_healthcheck.md) | Validates Kafka broker health, topic visibility, and consumer lag signals. | Async Microservices (Kafka) |
| [data_pipeline_observability.md](../../ops/runbooks/playbooks/data_pipeline_observability.md) | Comprehensive observability metrics for Kafka, Splunk, and storage pipelines with dashboards and alert thresholds. | Data Ingestion, Monitoring |
| [deployment_rollback_gitops.md](../../ops/runbooks/playbooks/deployment_rollback_gitops.md) | Executing a verified, safe rollback to a known-good state using GitOps tooling (ArgoCD/Flux). | All Application Deployments |
| [observability_dashboards.md](../../ops/runbooks/playbooks/observability_dashboards.md) | Building and validating dashboards for ingestion, storage, and system health. | Observability Stack |
| [securityhub_config.md](../../ops/runbooks/playbooks/securityhub_config.md) | Enabling AWS SecurityHub and Config with audit-ready evidence. | Cloud Security & Compliance |

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
