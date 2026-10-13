# Golden Platform Developer Onboarding Guide

Welcome to the Golden Platform development team. This guide gets you from zero to productive in 3 days.

---

## Day 1: Understanding Golden Platform Fundamentals

### Morning: Architecture Overview (2 hours)

**Goal:** Understand what Golden Platform does and how it's organized.

#### Step 1: Read the Architecture (30 minutes)
- Start: [Architecture Reference](../architecture/overview.md)
- Focus on: Purpose, Services, Technology Stack
- Key concept: Golden Platform = Reliability for Money & Healthcare

#### Step 2: Quick Platform Tour (30 minutes)
```bash
# Clone the platform
git clone https://github.com/Here2ServeU/nawex-platform
cd golden

# Explore directory structure
tree -L 2 -d golden/
# Output:
# golden/
# ├─ api/ (REST/OpenAPI; gRPC protos in proto/)
# ├─ multi-tenancy/ (Tenant isolation)
# ├─ security/ (Zero-trust, encryption)
# ├─ observability/ (Tracing, metrics, logs)
# ├─ testing/ (Unit, integration, chaos)
# └─ fintech/ (Transaction engine)
```

#### Step 3: Watch System in Action (1 hour)
```bash
# Start local Golden Platform (Docker Compose)
cd docker-compose
docker-compose -f compose.yaml up -d

# Wait 30 seconds for startup
sleep 30

# Test: Process a test transaction
curl -X POST http://localhost:8000/api/v2/tenants/test-tenant/transactions \
  -H "Authorization: Bearer test-token" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1000.00,
    "currency": "USD",
    "source_account": "ACC-001",
    "destination_account": "ACC-002"
  }'

# Expected: Transaction ID + fraud score
```

### Afternoon: Local Development Environment (3 hours)

**Goal:** Set up your workstation for Golden Platform development.

#### Prerequisites Check
```bash
# Required versions
python --version # 3.11+
docker --version # 24.0+
kubectl version # 1.25+
helm version # 3.12+

# Install missing tools
brew install python3.11 docker kubectl helm # macOS
apt install python3.11 docker.io kubectl helm # Ubuntu
```

#### OPA (policy tests)
The OPA version is pinned in `.opa-version`; CI installs the same one.
```bash
brew install opa                                  # macOS
scoop install opa   # or: choco install opa       # Windows
opa version && opa test security/policies/opa     # expect PASS on every test
```
Without a package manager, download the single binary for your OS from
https://openpolicyagent.org/downloads/ and put it on your `PATH`.

Check everything at once with `make doctor` (macOS/Linux/WSL) or
`pwsh scripts/doctor.ps1` (Windows PowerShell).

#### Python Environment Setup
```bash
cd src/golden/

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Verify installation
python -c "import golden; print(golden.__version__)"
# Output: golden 2.0.0
```

#### IDE Setup (VS Code)
```json
{
  "extensions": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "GitHub.copilot",
    "Kubernetes.vscode-kubernetes-tools",
    "ms-azuretools.vscode-docker",
    "ms-vscode.makefile-tools"
  ],
  "launch": {
    "version": "0.2.0",
    "configurations": [
      {
        "name": "Debug Fintech Processor",
        "type": "python",
        "request": "launch",
        "program": "${workspaceFolder}/golden/fintech/processor.py",
        "console": "integratedTerminal"
      }
    ]
  }
}
```

#### Local Kubernetes Cluster
```bash
# Option 1: Docker Desktop Kubernetes (easiest)
docker desktop > preferences > Kubernetes > Enable Kubernetes

# Option 2: Minikube
minikube start --cpus=8 --memory=16000 --disk-size=50gb

# Option 3: Kind (lighter weight)
kind create cluster --config kind-config.yaml

# Verify cluster
kubectl get nodes
kubectl get pods --all-namespaces
```

#### Deploy Local Golden Platform
```bash
# 1. Create namespace
kubectl create namespace golden-dev

# 2. Deploy with Helm
cd helm/
helm install golden . \
  --namespace golden-dev \
  --values values-local.yaml

# 3. Wait for services
kubectl wait --for=condition=Ready pod \
  -l app=fintech-processor \
  -n golden-dev \
  --timeout=300s

# 4. Expose services locally
kubectl port-forward -n golden-dev \
  svc/api-gateway 8000:80 &
kubectl port-forward -n golden-dev \
  svc/jaeger-ui 16686:16686 &

# 5. Test endpoints
curl http://localhost:8000/api/v2/health
# Output: {"status": "healthy"}
```

#### IDE Configuration
```bash
# Format Python code on save
pip install black
black src/golden/

# Lint issues
pip install pylint
pylint src/golden/

# Type checking
pip install mypy
mypy src/golden/

# All at once
make lint
```

### Evening: Core Concepts Deep Dive (2 hours)

**Goal:** Understand 3 critical Golden Platform concepts.

#### Concept 1: Multi-Tenancy
```python
# Scenario: You're building a feature that reads transactions

# WRONG - No tenant isolation
async def get_transaction(transaction_id: str):
    return await db.query("SELECT * FROM transactions WHERE id = ?", (transaction_id,))

# CORRECT - Enforces tenant isolation
from golden.multi_tenancy import TenantContext

async def get_transaction(transaction_id: str):
    tenant_id = TenantContext.get_current_tenant() # From auth token
    
    return await db.query(
        "SELECT * FROM transactions WHERE id = ? AND tenant_id = ?",
        (transaction_id, tenant_id)
    )
    # PostgreSQL RLS automatically filters by tenant_id
    # This is belt-and-suspenders: two layers of protection
```

**Key Learning:** Always retrieve tenant_id from TenantContext, never trust user input for isolation.

#### Concept 2: Observability
```python
# Scenario: You're implementing fraud detection

from opentelemetry import trace, metrics
from golden.observability import traced_operation

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

fraud_counter = meter.create_counter("golden.fraud.detection")
fraud_latency = meter.create_histogram("golden.fraud.latency_ms")

@traced_operation("assess_fraud_score")
async def assess_transaction(transaction: dict) -> float:
    """
    Automatically traced and timed:
    - Trace ID: links all related spans
    - Span name: assess_fraud_score
    - Attributes: function, module, success/failure
    - Duration: measured and exported to Prometheus
    """
    import time
    start = time.time()
    
    score = await fraud_model.predict(transaction)
    
    elapsed = (time.time() - start) * 1000
    fraud_latency.record(elapsed)
    fraud_counter.add(1, {"model": "lstm-v3"})
    
    return score

# This automatically:
# 1. Creates a span viewable in Jaeger
# 2. Records latency in Prometheus
# 3. Sets success/failure attributes
# 4. Links to parent request via trace ID
```

**Key Learning:** Use @traced_operation decorator on async functions; metrics are auto-collected.

#### Concept 3: Security > Everything
```python
# Scenario: Storing account numbers

from golden.security import VaultClient
from golden.multi_tenancy import TenantContext

vault = VaultClient()

# WRONG - Storing plaintext in database
def store_account(account_number: str):
    db.insert("accounts", {"number": account_number})

# CORRECT - Encrypt before storage
async def store_account(account_number: str):
    tenant_id = TenantContext.get_current_tenant()
    
    # Encrypt via Vault Transit Engine
    encrypted = await vault.encrypt(
        mount_point="transit",
        name=f"golden-{tenant_id}-account",
        plaintext=account_number
    )
    
    # Store encrypted value
    db.insert("accounts", {
        "encrypted_number": encrypted,
        "tenant_id": tenant_id
    })

# Retrieval: Vault automatically decrypts with tenant-specific key
encrypted_account = db.query("SELECT encrypted_number FROM accounts WHERE id = ?")
plaintext = await vault.decrypt(encrypted_account)
```

**Key Learning:** Zero trust - authenticate everything, encrypt by default, validate at every layer.

---

## Day 2: Write Your First Feature

### Morning: Understanding the Codebase (2 hours)

**Goal:** Navigate Golden Platform's code organization and understand patterns.

#### Service Architecture

```
src/golden/fintech/
├─ processor.py (Main business logic)
├─ router.py (API endpoints)
├─ models.py (Data models + validation)
├─ schema.py (Database schema)
├─ observability.py (Metrics + tracing)
└─ tests/
   ├─ unit/
   ├─ integration/
   └─ fixtures/
```

#### Code Reading Exercise: Fraud Detection

```bash
# 1. Understand the endpoint
cat src/golden/fintech/router.py | grep -A 20 "process_transaction"

# 2. Read the business logic
cat src/golden/fintech/processor.py | grep -A 30 "async def process"

# 3. Check the models
cat src/golden/fintech/models.py | grep -A 10 "class Transaction"

# 4. See how it's tested
cat src/golden/fintech/tests/integration/test_processor.py
```

#### Key Files to Know

| File | Purpose | When You Need It |
|------|---------|-----------------|
| `src/golden/api/decorators.py` | Auth, validation, tracing | Every endpoint |
| `src/golden/multi_tenancy/context.py` | Get current tenant | Data access |
| `src/golden/security/encryption.py` | Encrypt/decrypt fields | Handle PII/PHI |
| `src/golden/observability/tracing.py` | Add custom spans | New features |
| `src/golden/tests/fixtures.py` | Test data + mocks | Write tests |

### Afternoon: Write a Feature (3 hours)

**Task:** Add a transaction fee calculation feature.

#### Step 1: Create Feature Branch
```bash
git checkout -b feat/transaction-fees
```

#### Step 2: Write the Business Logic
```python
# src/golden/fintech/fees.py
from decimal import Decimal
from golden.observability import traced_operation
from golden.multi_tenancy import TenantContext

@traced_operation("calculate_transaction_fee")
async def calculate_fee(amount: Decimal, transaction_type: str) -> Decimal:
    """
    Calculate transaction fee based on amount and type.
    Fee structure:
    - Domestic transfer <$10k: 0.1%
    - Domestic transfer $10k+: 0.05%
    - International: 1%
    """
    tenant_id = TenantContext.get_current_tenant()
    
    # Get tenant's fee schedule
    fee_schedule = await get_tenant_fee_schedule(tenant_id)
    
    if transaction_type == "international":
        percentage = fee_schedule.get("international_percent", Decimal("1.0"))
    elif amount > Decimal("10000"):
        percentage = fee_schedule.get("high_amount_percent", Decimal("0.05"))
    else:
        percentage = fee_schedule.get("standard_percent", Decimal("0.1"))
    
    fee = (amount * percentage) / Decimal("100")
    
    # Record metric
    fee_meter.record(float(fee), {"type": transaction_type})
    
    return fee
```

#### Step 3: Create API Endpoint
```python
# src/golden/fintech/router.py
from fastapi import APIRouter, Depends
from golden.api.decorators import require_auth, validate_tenant

router = APIRouter(prefix="/api/v2/tenants/{tenant_id}")

@router.post("/transactions/{transaction_id}/fees")
@require_auth(scopes=["golden:read:transactions"])
@validate_tenant()
async def calculate_transaction_fee(
    tenant_id: str,
    transaction_id: str,
    current_user = Depends(get_current_user)
):
    """
    GET /api/v2/tenants/{tenant_id}/transactions/{transaction_id}/fees
    Returns: { "amount": 50.00, "percent": 0.1 }
    """
    # Get transaction
    transaction = await get_transaction(transaction_id, tenant_id)
    
    # Calculate fee
    fee = await calculate_fee(transaction.amount, transaction.type)
    
    return {
        "transaction_id": transaction_id,
        "amount": float(fee),
        "percent": float(percentage),
        "calculated_at": datetime.utcnow()
    }
```

#### Step 4: Write Tests

**Unit Test (tests business logic)**
```python
# src/golden/fintech/tests/unit/test_fees.py
import pytest
from decimal import Decimal
from hypothesis import given, strategies as st
from golden.fintech.fees import calculate_fee

@pytest.mark.asyncio
async def test_domestic_small_amount():
    fee = await calculate_fee(Decimal("5000"), "domestic")
    assert fee == Decimal("5") # 0.1%

@pytest.mark.asyncio
async def test_domestic_large_amount():
    fee = await calculate_fee(Decimal("50000"), "domestic")
    assert fee == Decimal("25") # 0.05%

@pytest.mark.asyncio
async def test_international():
    fee = await calculate_fee(Decimal("1000"), "international")
    assert fee == Decimal("10") # 1%

@given(st.decimals(min_value=Decimal("1"), max_value=Decimal("1000000")))
async def test_fee_is_positive(amount):
    fee = await calculate_fee(amount, "domestic")
    assert fee > Decimal("0")
```

**Integration Test (tests whole flow)**
```python
# src/golden/fintech/tests/integration/test_fee_endpoint.py
@pytest.mark.asyncio
async def test_calculate_fee_endpoint(client, transaction_processor):
    # Setup: Create a transaction
    transaction = await transaction_processor.process(...)
    
    # Act: Calculate fee
    response = await client.post(
        f"/api/v2/tenants/test-tenant/transactions/{transaction.id}/fees"
    )
    
    # Assert
    assert response.status_code == 200
    assert response.json()["amount"] > 0
```

#### Step 5: Run Tests
```bash
# Unit tests
pytest src/golden/fintech/tests/unit/test_fees.py -v

# Integration tests
pytest src/golden/fintech/tests/integration/test_fee_endpoint.py -v

# Coverage
pytest --cov=golden.fintech.fees --cov-report=html

# All at once
make test
```

#### Step 6: Commit & Push
```bash
# Stage changes
git add src/golden/fintech/fees.py
git add src/golden/fintech/router.py
git add src/golden/fintech/tests/

# Commit with clear message
git commit -m "feat(fintech): add transaction fee calculation

- Implement calculate_fee() with tenant-aware fee schedules
- Add POST /api/v2/tenants/{tenant_id}/transactions/{id}/fees endpoint
- Include unit tests with property-based testing
- Include integration test for full endpoint
- Auto-instrumented with OpenTelemetry tracing
- Latency: <5ms (no external calls)"

# Create pull request
git push origin feat/transaction-fees
# Then: Open PR on GitHub
```

---

## Day 3: Explore Advanced Topics

### Morning: Security Deep Dive (2 hours)

**Goal:** Understand Golden Platform's security model.

#### 1. Multi-Tenant Isolation
```bash
# Demo: Verify RLS isolation
kubectl port-forward -n golden-dev svc/postgres 5432:5432

psql -h localhost -U golden -d golden

-- Login as tenant-a
SET app.current_tenant_id = 'tenant-a';
SELECT * FROM transactions;
-- Result: Only tenant-a's transactions

-- Try to bypass with WHERE clause
SELECT * FROM transactions WHERE tenant_id = 'tenant-b';
-- Result: Still filtered to tenant-a (RLS enforces)
```

#### 2. Field-Level Encryption
```python
# Demo: Encrypt and decrypt
from golden.security import VaultClient

vault = VaultClient()

# Encrypt
plaintext = "123-45-6789"
ciphertext = vault.encrypt("account-number", plaintext)
# Result: vault:v1:abc123def456...

# Decrypt (only service accounts with permission)
plaintext = vault.decrypt("account-number", ciphertext)
# Result: 123-45-6789 (only if decoded with correct tenant's key)
```

#### 3. Zero-Trust in Action
```bash
# Demo: Service-to-service authentication

# Without Istio mTLS: Service A → Service B (unencrypted)
curl http://fraud-detector:8000/assess

# With Istio mTLS: Service A → Service B (encrypted + authenticated)
# 1. Service A's Envoy sidecar gets certificate (SPIFFE/SVID)
# 2. Service B's Envoy validates A's certificate
# 3. Data flows through encrypted mTLS tunnel
# 4. Both sides authenticated (zero trust)
```

### Afternoon: Production-Ready Features (2 hours)

**Goal:** Learn what makes code production-ready.

#### Checklist: Before Shipping Code

```markdown
## Functionality
- [ ] Feature works in happy path (no errors)
- [ ] Edge cases handled (empty input, null, etc)
- [ ] Error handling with useful messages
- [ ] Idempotency (retried requests don't create duplicates)

## Testing
- [ ] Unit tests (>80% coverage)
- [ ] Integration tests (full flow)
- [ ] Property-based tests (hypothesis)
- [ ] Error scenario tests

## Security
- [ ] Input validation + sanitization
- [ ] No secrets in logs (passwords, tokens)
- [ ] Tenant isolation verified
- [ ] Encryption for sensitive data
- [ ] OWASP Top 10 checked

## Observability
- [ ] @traced_operation on async functions
- [ ] Metrics recorded for business events
- [ ] Error events logged with context
- [ ] Latency tracked (histogram)
- [ ] Request tracing enabled (thread-local context)

## Performance
- [ ] Latency acceptable (<100ms for most ops)
- [ ] No N+1 queries (use JOIN)
- [ ] Connection pooling used
- [ ] Cache TTLs appropriate
- [ ] Load tested at 10x expected volume

## Documentation
- [ ] Docstrings on functions (what, why, example)
- [ ] README updated with new endpoints
- [ ] Configuration documented
- [ ] Examples for other developers
- [ ] Breaking changes documented

## Deployment
- [ ] Backward compatible (if list→dict, handle both)
- [ ] Database migration tested (with data)
- [ ] Config changes documented
- [ ] Rollback tested
- [ ] Monitoring alerts set up
```

#### Example: Production-Ready Transaction API

```python
# First draft (not production-ready)
async def process_transaction(tenant_id, amount, source_account, dest_account):
    result = fraud_model.predict(amount, source_account)
    db.insert("transactions", {...})
    return {"id": transaction_id}

# Production-ready
from golden.api.decorators import require_auth, validate_input, trace_span
from golden.multi_tenancy import TenantContext
from golden.observability import traced_operation
from golden.security import validate_no_injection
import logging

logger = logging.getLogger(__name__)
transaction_counter = meter.create_counter("golden.transaction.processed")

@traced_operation("process_transaction")
async def process_transaction(
    tenant_id: str,
    amount: Decimal,
    source_account: str,
    dest_account: str,
    idempotency_key: str | None = None
) -> dict:
    """
    Process a financial transaction with fraud detection.
    
    Args:
        tenant_id: The tenant making the request
        amount: Transaction amount (positive Decimal)
        source_account: Source account ID (length 10-20)
        dest_account: Destination account ID (length 10-20)
        idempotency_key: Optional key for retry safety (UUID format)
    
    Returns:
        {"id": "TXN-...", "fraud_score": 0.02, "status": "SETTLED"}
    
    Raises:
        ValidationError: If input invalid
        InsufficientFundsError: If source account balance too low
        
    Example:
        >>> result = await process_transaction(
        ... "acme-bank",
        ... Decimal("1000.00"),
        ... "ACC-001",
        ... "ACC-002"
        ... )
        >>> print(result["id"])
        "TXN-20260218-0001"
    """
    
    # 1. Validate tenant
    current_tenant = TenantContext.get_current_tenant()
    assert current_tenant == tenant_id, "Tenant mismatch"
    
    # 2. Validate input
    validate_no_injection(source_account)
    validate_no_injection(dest_account)
    assert amount > 0, "Amount must be positive"
    assert amount < Decimal("1000000000"), "Amount exceeds limit"
    
    # 3. Idempotency check
    if idempotency_key:
        existing = db.query("transactions", {"idempotency_key": idempotency_key})
        if existing:
            return existing # Replay previous response
    
    try:
        # 4. Assess fraud
        fraud_score = await fraud_model.assess(amount, source_account)
        
        # 5. Store transaction
        transaction = Transaction(
            id=generate_transaction_id(),
            tenant_id=tenant_id,
            amount=amount,
            source_account=source_account,
            destination_account=dest_account,
            fraud_score=fraud_score,
            status="PROCESSING",
            idempotency_key=idempotency_key,
            created_at=datetime.utcnow()
        )
        db.insert("transactions", transaction)
        
        # 6. Attempt settlement
        settlement = await settlement_engine.settle(transaction)
        transaction.status = "SETTLED"
        db.update("transactions", transaction)
        
        # 7. Record metrics
        transaction_counter.add(1, {"currency": "USD", "fraud_decision": fraud_score > 0.7})
        
        # 8. Log success
        logger.info(
            "Transaction processed successfully",
            extra={
                "transaction_id": transaction.id,
                "amount": float(amount),
                "fraud_score": fraud_score,
                "request_id": get_request_id(),
                "tenant_id": tenant_id
            }
        )
        
        return {
            "id": transaction.id,
            "fraud_score": float(fraud_score),
            "status": "SETTLED",
            "created_at": transaction.created_at.isoformat()
        }
    
    except Exception as e:
        # 9. Handle errors gracefully
        logger.error(
            "Transaction processing failed",
            exc_info=True,
            extra={
                "amount": float(amount),
                "error_type": type(e).__name__,
                "tenant_id": tenant_id,
                "request_id": get_request_id()
            }
        )
        raise
```

---

## Continuation: Next Steps

### Week 2-4: Deeper Learning
- [ ] Complete [Enterprise Testing Framework](enterprise-testing.md)
- [ ] Study [Security Architecture](../architecture/zero-trust.md)
- [ ] Learn [Observability Stack](../architecture/advanced-observability.md)

### Month 2: Contribution Opportunities
- [ ] Fix 5+ GitHub issues (labeled "good-first-issue")
- [ ] Implement 1 feature with mentor oversight
- [ ] Write 10+ unit tests
- [ ] Participate in code reviews

### Month 3: Advanced Topics
- [ ] Study chaos engineering scenarios
- [ ] Implement monitoring for your service
- [ ] Participate in on-call rotation (shadow)
- [ ] Present learning to team

---

## Troubleshooting

### Problem: `ImportError: No module named 'golden'`
```bash
# Solution: Ensure you're in virtual environment
source venv/bin/activate
pip install -e . # Install in editable mode
```

### Problem: Tests timeout in Docker
```bash
# Solution: Increase resource limits
docker-compose up -d --scale postgres=2
# Or: docker desktop preferences > resources > increase RAM/CPU
```

### Problem: Permission denied on local cluster
```bash
# Solution: Fix Kubernetes auth
kubectl config use-context docker-desktop
kubectl auth can-i create deployments --namespace=golden-dev
```

### Problem: Can't connect to local Postgres
```bash
# Solution: Verify port forwarding
kubectl port-forward -n golden-dev svc/postgres 5432:5432
# In another terminal:
psql -h localhost -U golden -d golden
```

---

## Getting Help

- **Documentation:** [docs.golden-platform.example](https://docs.golden-platform.example)
- **GitHub Issues:** [github.com/Here2ServeU/nawex-platform/issues](https://github.com/Here2ServeU/nawex-platform/issues)
- **Slack:** #golden-developers (internal)
- **Office Hours:** Thursdays 2-3pm PST
- **Mentor:** Your assigned engineering buddy

---

## Quick Reference

### Common Commands
```bash
# Run tests
pytest golden/ # All tests
pytest -k fraud # Tests matching "fraud"
pytest -m unit # Only unit tests (not integration)
pytest --cov=golden --cov-report=html # Coverage report
make test # Everything at once

# Start development environment
docker-compose -f compose.yaml up -d
kubectl logs -f deployment/fintech-processor -n golden-dev

# Format code
black src/golden/ --line-length=100
isort src/golden/ # Sort imports

# Type checking
mypy src/golden/ --strict

# Deploy locally
helm install golden helm/ -f values-local.yaml --namespace golden-dev
```

---

## Success Criteria

By end of Day 3, you should be able to:
- [ ] Explain Golden Platform's architecture (services, data flow, security)
- [ ] Deploy Golden Platform locally (kubernetes + services running)
- [ ] Write a feature (code + tests + documentation)
- [ ] Understand multi-tenancy and security model
- [ ] Access observability dashboards (Jaeger, Prometheus, Grafana)
- [ ] Commit code with proper message format

Welcome to the team!

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
