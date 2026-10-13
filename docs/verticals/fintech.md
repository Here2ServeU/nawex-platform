# Fintech Services Module

This directory contains the containerized microservices for the **Fintech** vertical of the **Golden Platform**. These services handle real-time transaction processing, fraud detection, and payment gateway simulation.

**Golden Platform** introduces a pre-settlement ML inference layer that intercepts transation flow before ledger finalization. 

The fraud scoring engine runs an explainable 5-signal composite score (amount, velocity, geo, channel, MCC) with a 50 ms latency budget as the design target. Measured in-process (no network, laptop) at p95 ≈ 2 ms; end-to-end latency under load is not yet measured — see [CLAIMS.md](../CLAIMS.md). 

## Production-Grade Architecture
```
┌────────────────────────────────────────────────────┐
│                   Presentation Layer               │
│                Client / API Gateway                │
└────────────────────────────────────────────────────┘
                          │
┌────────────────────────────────────────────────────┐
│                Core Processing Layer               │
│  Transaction Engine (Idempotent + Kafka-backed)    │
└────────────────────────────────────────────────────┘
            │                        │
            ▼                        ▼
┌──────────────────────┐   ┌──────────────────────┐
│ Fraud Detection      │   │ Payment Gateway      │
│ Scoring (50ms budget)│   │ Processor Routing    │
└──────────────────────┘   └──────────────────────┘
            │
            ▼
┌──────────────────────┐
│ Fintech Redis Cache  │
└──────────────────────┘

┌────────────────────────────────────────────────────┐
│                Observability & Control             │
│ Fintech Watchdog – SLO + Compliance Monitoring     │
└────────────────────────────────────────────────────┘
```

This FinTech Domain is composed of 5 bounded services: 
- **Transation Engine** acts as the orchestration core: it validates transactions and gates them inline on the fraud score. Kafka-backed event sourcing and replay are a design target; the current service keeps state in memory. 
- Before any transction proceeds to settlement, it is intercepted by the **Fraud Detector**, which computes an explainable 5-signal fraud score (`src/golden/ai/pipelines/detect_fraud.py`). LSTM/TCN models are used for SLI forecasting, not fraud scoring. 
- **FinTech Redis** provides low-latency state caching for transation context and rate limiting. 
- The **Payment Gateway Simulator** abstracts processor integrations and supports latency injection for resilience testing. 
- The **FinTech Watchdog** continuously monitors SLO adherence, fraud latency tresholds, and compliance posture, supporting PCI-DSS alignment (mapping, not certification). 

## Services

### Transaction Engine (`transaction-engine`)
- **Port**: 8090
- **Purpose**: Core payment processing service that receives, validates, and routes financial transactions.
- **Features**: Validation, inline fraud gating, settlement status. Kafka-backed event sourcing and PCI-DSS-scoped data handling (tokenization) are design targets.

### Fraud Detector (`fraud-detector`)
- **Port**: 8091
- **Purpose**: Real-time explainable fraud scoring (5 weighted signals with per-account behavioural history).
- **Features**: 50 ms latency budget (in-process p95 ≈ 2 ms measured), configurable threshold (`FRAUD_THRESHOLD`), model version reported at `/model`. A trained fraud model with a gated registry and rollback is managed separately by `golden model`.
- **Pipeline**: Uses `src/golden/ai/pipelines/detect_fraud.py` for scoring logic.

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
# From the project root directory (not fintech/)
# Start all fintech services (requires Kafka)
docker compose up -d transaction-engine fraud-detector payment-gateway

# Or use the convenience script
make up
```

## Verify Services

Once the services are running, check their health in the browser or with `curl`:

| Service            | Health Check URL                  |
|--------------------|-----------------------------------|
| Transaction Engine | http://localhost:8090/health       |
| Fraud Detector     | http://localhost:8091/health       |
| Payment Gateway    | http://localhost:8092/health       |

## API Endpoints

### Transaction Engine (`:8090`)

| Method | Endpoint                     | Description             |
|--------|------------------------------|-------------------------|
| GET    | `/health`                    | Health status           |
| GET    | `/metrics`                   | Prometheus metrics      |
| POST   | `/api/v1/transactions`       | Submit a transaction    |
| GET    | `/api/v1/transactions`       | List transactions       |
| GET    | `/api/v1/settlement/status`  | Settlement status       |
| POST   | `/ops/chaos/latency`         | Inject latency (chaos)  |
| POST   | `/ops/chaos/error`           | Inject errors (chaos)   |

### Fraud Detector (`:8091`)

| Method | Endpoint       | Description                     |
|--------|----------------|---------------------------------|
| GET    | `/health`      | Health status                   |
| GET    | `/metrics`     | Prometheus metrics              |
| POST   | `/score`       | Score a transaction for fraud   |
| POST   | `/model/swap`  | Hot-swap the fraud model        |

### Payment Gateway (`:8092`)

| Method | Endpoint                      | Description               |
|--------|-------------------------------|---------------------------|
| GET    | `/health`                     | Health status             |
| GET    | `/metrics`                    | Prometheus metrics        |
| POST   | `/api/v1/process`             | Process a payment         |
| POST   | `/api/v1/settlement/trigger`  | Trigger settlement batch  |
| GET    | `/api/v1/settlement/batches`  | List settlement batches   |
| POST   | `/ops/chaos/latency`          | Inject latency (chaos)    |
| POST   | `/ops/chaos/error`            | Inject errors (chaos)     |
| POST   | `/ops/reset`                  | Reset chaos injections    |

## Usage Examples

**Submit a transaction:**
```bash
curl -X POST http://localhost:8090/api/v1/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 150.00,
    "currency": "USD",
    "sender": "acct_001",
    "receiver": "acct_002",
    "type": "payment"
  }'
```

**Score a transaction for fraud:**
```bash
curl -X POST http://localhost:8091/score \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn_123",
    "amount": 150.00,
    "sender": "acct_001",
    "receiver": "acct_002"
  }'
```

**Process a payment through the gateway:**
```bash
curl -X POST http://localhost:8092/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 150.00,
    "currency": "USD",
    "method": "card",
    "sender": "acct_001",
    "receiver": "acct_002"
  }'
```

## Validation

After running the usage examples above, validate the results:

**Check the transaction response (pretty-printed):**
```bash
curl -s -X POST http://localhost:8090/api/v1/transactions \
  -H "Content-Type: application/json" \
  -d '{"amount":150.00,"currency":"USD","sender":"acct_001","receiver":"acct_002","type":"payment"}' | python3 -m json.tool
```

**List transactions to confirm it was recorded:**
```bash
curl -s http://localhost:8090/api/v1/transactions | python3 -m json.tool
```

**Check settlement status:**
```bash
curl -s http://localhost:8090/api/v1/settlement/status | python3 -m json.tool
```

**Check health of all services:**
```bash
curl -s http://localhost:8090/health | python3 -m json.tool
curl -s http://localhost:8091/health | python3 -m json.tool
curl -s http://localhost:8092/health | python3 -m json.tool
```

**Check metrics:**
```bash
curl -s http://localhost:8090/metrics
curl -s http://localhost:8091/metrics
curl -s http://localhost:8092/metrics
```

**Check container logs for errors:**
```bash
docker compose logs transaction-engine --tail 20
docker compose logs fraud-detector --tail 20
docker compose logs payment-gateway --tail 20
```

> **Tip:** Piping through `python3 -m json.tool` pretty-prints JSON responses for easier reading.

## Compliance

These services are designed to comply with:
- **PCI-DSS v4.0** — Cardholder data protection
- **SOX** — Financial reporting controls
- **PSD2** — Strong Customer Authentication
- **GLBA** — Financial privacy safeguards

See `/docs/compliance/` for detailed compliance mappings.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
