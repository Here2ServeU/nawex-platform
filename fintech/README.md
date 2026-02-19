# Fintech Services Module

This directory contains the containerized microservices for the **Fintech** vertical of the Naweji Reliability Platform (NRP). These services handle real-time transaction processing, fraud detection, and payment gateway simulation.

## Services

### Transaction Engine (`transaction-engine`)
- **Port**: 8090
- **Purpose**: Core payment processing service that receives, validates, and routes financial transactions.
- **Features**: Kafka-backed event sourcing, idempotent transaction processing, PCI-DSS compliant data handling.

### Fraud Detector (`fraud-detector`)
- **Port**: 8091
- **Purpose**: Real-time ML-based fraud scoring service using LSTM/TCN models.
- **Features**: Sub-50ms scoring latency, configurable thresholds, automatic model hot-swap.
- **Pipeline**: Uses `/ai/pipelines/detect_fraud.py` for scoring logic.

### Payment Gateway Simulator (`payment-gateway`)
- **Port**: 8092
- **Purpose**: Simulates payment processor interactions for development and demo purposes.
- **Features**: Configurable latency/error injection, settlement batch processing, multi-currency support.

### Fintech Redis (`fintech-redis`)
- **Port**: 6380
- **Purpose**: Dedicated high-performance cache for transaction state, fraud scoring results, and rate limiting.

### Fintech Watchdog (`fintech-watchdog`)
- **Purpose**: Continuous compliance monitoring for payment SLOs, fraud detection latency, and settlement pipeline health.

## Quick Start

```bash
# Start all fintech services (requires Kafka)
docker compose up -d transaction-engine fraud-detector payment-gateway fintech-redis fintech-watchdog

# Or use the convenience script
scripts/start_fintech.sh
```

## Compliance

These services are designed to comply with:
- **PCI-DSS v4.0** — Cardholder data protection
- **SOX** — Financial reporting controls
- **PSD2** — Strong Customer Authentication
- **GLBA** — Financial privacy safeguards

See `/docs/compliance/` for detailed compliance mappings.

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
