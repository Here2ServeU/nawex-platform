# NERP Quick Start (5 Minutes)

Get NERP running locally in 5 minutes and process your first transaction.

---

## Prerequisites (2 minutes setup)

**Minimum Requirements:**
- Docker Desktop 24.0+
- Git
- `curl` command-line tool

**Installation:**
```bash
# Download Docker Desktop
# https://www.docker.com/products/docker-desktop

# Verify installation
docker --version # Should print: Docker version 24.0+
docker-compose --version # Should print: Docker Compose version 2.0+
```

---

## Start NERP (2 minutes)

```bash
# 1. Clone repository (1 minute)
git clone https://github.com/naweji/nerp.git
cd nerp

# 2. Start services with Docker Compose (1 minute)
docker-compose -f docker-compose.nerp.yml up -d

# 3. Wait for services to start
sleep 30

# 4. Verify everything is running
docker-compose ps

# Expected output:
# NAME STATUS
# nerp-api-gateway Up 10 seconds
# nerp-fintech-processor Up 12 seconds
# nerp-fraud-detector Up 11 seconds
# nerp-postgres Up 15 seconds
# nerp-kafka Up 14 seconds
# nerp-jaeger Up 13 seconds
# nerp-prometheus Up 12 seconds
```

---

## Process Your First Transaction (1 minute)

```bash
# 1. Get an auth token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "demo"}' \
  | jq -r '.token')

echo "Token: $TOKEN"

# 2. Process a transaction
curl -X POST http://localhost:8000/api/v2/tenants/demo-tenant/transactions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1000.00,
    "currency": "USD",
    "source_account": "ACC-001",
    "destination_account": "ACC-002"
  }' | jq .

# Expected response:
# {
# "id": "TXN-20260218-0001",
# "status": "SETTLED",
# "fraud_score": 0.02,
# "fraud_decision": "APPROVE",
# "settlement_time": "2026-02-18T14:30:00.075Z",
# "confidence": 0.98
# }
```

---

## Explore the Platform (5 minutes - optional)

### View Transaction Traces
```bash
# Open Jaeger UI
open http://localhost:16686

# Search for your transaction:
# 1. Select Service: fintech-processor
# 2. Click "Find Traces"
# 3. Click a trace to see the full path
# - Fraud detection latency: 40ms
# - Settlement latency: 20ms
# - Total: 75ms
```

### View Metrics
```bash
# Open Prometheus
open http://localhost:9090

# Try these queries in the search box:
rate(nerp_transaction_processed[1m]) # Transactions/sec
histogram_quantile(0.99, nerp_transaction_latency_ms) # P99 latency
```

### View Logs
```bash
# Stream logs from fintech processor
docker-compose logs -f nerp-fintech-processor

# You should see your transaction:
# [2026-02-18 14:30:00] INFO fintech_processor: Transaction TXN-001 processed
# - Amount: $1,000.00
# - Fraud Score: 0.02
# - Duration: 75ms
# - Request ID: 550e8400-e29b-41d4-a716-446655440000
```

---

## Stop Everything (30 seconds)

```bash
docker-compose down

# To remove volumes (database, etc.)
docker-compose down -v
```

---

## Next Steps

### Learn NERP
- [Architecture Reference](ARCHITECTURE_REFERENCE.md) - Complete system overview
- [Developer Onboarding](DEVELOPER_ONBOARDING.md) - 3-day learning path
- [API Documentation](api/API_SPECIFICATIONS.md) - All available endpoints

### Deploy to Kubernetes
See: [Deployment Guide](../../docs/guides/DEPLOYMENT.md)

### Run Tests
```bash
# Unit tests
docker-compose run nerp-tests pytest tests/unit -v

# Integration tests
docker-compose run nerp-tests pytest tests/integration -v

# All tests
docker-compose run nerp-tests pytest
```

### Write Your First Feature
See: [Developer Onboarding - Day 2](DEVELOPER_ONBOARDING.md#day-2-write-your-first-feature)

---

## Troubleshooting

**Problem: Port 8000 already in use**
```bash
# Find process using port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or: Use different port
docker-compose run -p 9000:8000 nerp-api-gateway
```

**Problem: Docker containers not starting**
```bash
# Check Docker daemon
docker info

# Increase Docker resources
# Docker Desktop > Preferences > Resources > CPU: 4+, Memory: 8GB+

# Restart Docker
docker restart
```

**Problem: Postgres connection refused**
```bash
# Wait longer for startup
sleep 60

# Check Postgres logs
docker-compose logs nerp-postgres

# Recreate Postgres volume
docker-compose down -v
docker-compose up -d nerp-postgres
```

**Problem: Can't get auth token**
```bash
# Check if API gateway is healthy
curl http://localhost:8000/health

# If unhealthy, restart
docker-compose restart nerp-api-gateway

# Try demo credentials
# Username: demo
# Password: demo
```

---

## API Endpoints (Quick Reference)

### Fintech
```
POST /api/v2/tenants/{tenantId}/transactions # Process transaction
GET /api/v2/tenants/{tenantId}/transactions # List transactions
GET /api/v2/tenants/{tenantId}/transactions/{id} # Get transaction
POST /api/v2/tenants/{tenantId}/transactions/{id}/approve # Manual approve
```

### Healthcare
```
POST /api/v2/tenants/{tenantId}/patients # Admit patient
PUT /api/v2/tenants/{tenantId}/patients/{id}/vitals # Record vitals
GET /api/v2/tenants/{tenantId}/patients/{id} # Get patient
GET /api/v2/tenants/{tenantId}/patients/{id}/alerts # Get alerts
```

### Monitoring
```
GET /health # Service health check
GET /metrics # Prometheus metrics
GET /api/v2/debug/spans # Recent traces (dev only)
```

---

## Demo Credentials

```
Username: demo
Password: demo
Tenant ID: demo-tenant
API Key: sk_demo_abc123xyz

Test Accounts:
- Source: ACC-001 (Balance: $1,000,000)
- Destination: ACC-002 (Balance: $0)
```

---

## Success Indicators

 You've successfully completed the quick start when:
- [ ] NERP services are running (docker-compose ps shows all "Up")
- [ ] You can process a transaction (curl command returns 200)
- [ ] Transaction shows in Jaeger trace view
- [ ] P99 latency appears in Prometheus
- [ ] Transaction log appears in Docker logs

 Congratulations! You're running NERP.

---

## Share Your Feedback

- **Questions?** [GitHub Discussions](https://github.com/naweji/nerp/discussions)
- **Found a bug?** [GitHub Issues](https://github.com/naweji/nerp/issues)
- **Want to learn more?** [Full Documentation](https://docs.nerp-platform.io)
- **Enterprise support?** support@nerp-platform.io

---

**Ready for production deployment?**
→ See [Deployment Guide](../../docs/guides/DEPLOYMENT.md)

**Want to modify NERP?**
→ See [Developer Onboarding](DEVELOPER_ONBOARDING.md)

**Need security/compliance details?**
→ See [Security Architecture](security/ZERO_TRUST_ARCHITECTURE.md)

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
