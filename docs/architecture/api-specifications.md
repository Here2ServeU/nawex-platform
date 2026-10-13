# Golden Platform API Specifications

## Three-API Strategy

Golden Platform provides three API options for maximum flexibility:

1. **REST API** - Standard JSON endpoints (70% of use cases)
2. **GraphQL API** - Efficient data querying (20% of use cases)
3. **gRPC** - High-performance services (10% of use cases)

---

## REST API v2

### Design Principles
- JSON:API compliance
- Consistent error handling
- Request validation
- Rate limiting per tenant
- Resource versioning
- Comprehensive logging

### Base URL
```
https://api.golden-platform.example/api/v2/tenants/{tenantId}
```

### Authentication
```bash
# OAuth2 with PKCE
curl -X GET https://api.golden-platform.example/api/v2/tenants/TENANT-ID/transactions \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Content-Type: application/json"
```

### Core Endpoints

#### Fintech - Transactions
```
POST /api/v2/tenants/{tenantId}/transactions
       ├─ Request: { amount, currency, source_account, dest_account }
       ├─ Response: { id, status, fraud_score, estimated_delivery }
       └─ Latency: <50ms (fraud detection included)

GET /api/v2/tenants/{tenantId}/transactions/{id}
       ├─ Response: { id, status, audit_trail }
       └─ Latency: <10ms

GET /api/v2/tenants/{tenantId}/transactions?filter[status]=PENDING&limit=100
       ├─ Pagination: limit, offset, sort
       ├─ Filtering: status, date_range, amount_range
       ├─ Response: { data: [], total, pagination }
       └─ Latency: <100ms

POST /api/v2/tenants/{tenantId}/transactions/{id}/approve
       ├─ Admin override for manual review
       └─ Response: { approved_by, approved_at, settlement_time }

POST /api/v2/tenants/{tenantId}/transactions/{id}/reverse
       ├─ Reverse a transaction (if not settled)
       └─ Response: { reversed_at, reversal_id, new_balance }
```

**Example Request:**
```bash
curl -X POST https://api.golden-platform.example/api/v2/tenants/acme-bank/transactions \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1000.00,
    "currency": "USD",
    "source_account": "ACC-12345",
    "destination_account": "ACC-67890",
    "reference": "Invoice-2026-001",
    "metadata": {
      "invoice_id": "INV-001",
      "customer_id": "CUST-123"
    }
  }'

# Response (50ms later)
{
  "id": "TXN-20260218-001",
  "status": "PROCESSING",
  "fraud_score": 0.02,
  "fraud_decision": "APPROVE",
  "confidence": 0.98,
  "estimated_settlement": "2026-02-18T14:35:00Z",
  "audit": {
    "created_at": "2026-02-18T14:30:00Z",
    "requested_by": "service-account-1",
    "request_id": "REQ-UUID"
  }
}
```

#### Healthcare - Patients
```
POST /api/v2/tenants/{tenantId}/patients
       ├─ Admit new patient
       └─ Response: { patient_id, mrn, admission_date }

PUT /api/v2/tenants/{tenantId}/patients/{patientId}/vitals
       ├─ Record vital signs
       └─ Response: { recorded_at, alerts: [] }

GET /api/v2/tenants/{tenantId}/patients/{patientId}
       ├─ Get patient demographics and history
       └─ Response: { patient_data (FHIR format) }

GET /api/v2/tenants/{tenantId}/patients/{patientId}/alerts
       ├─ Get clinical alerts (last 24h)
       ├─ Filtering: severity (LOW, MEDIUM, HIGH, CRITICAL)
       └─ Response: { alerts: [], alert_count }

POST /api/v2/tenants/{tenantId}/clinical/decisions
       ├─ Request clinical decision support
       ├─ Input: { patient_id, vitals, symptoms }
       └─ Response: { recommendation, confidence, evidence }
```

**Example Request:**
```bash
curl -X PUT https://api.golden-platform.example/api/v2/tenants/hospital-a/patients/P-2026-001/vitals \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-02-18T14:30:00Z",
    "heart_rate": 72,
    "blood_pressure": "120/80",
    "temperature_celsius": 37.2,
    "oxygen_saturation": 0.98,
    "respiratory_rate": 16
  }'

# Response (<100ms)
{
  "recorded_at": "2026-02-18T14:30:00Z",
  "patient_id": "P-2026-001",
  "vitals_id": "VIT-001",
  "alerts": [
    {
      "alert_id": "ALT-001",
      "severity": "MEDIUM",
      "message": "Blood pressure elevated (120/80)",
      "detected_by": "vital-baseline-model",
      "confidence": 0.75
    }
  ],
  "clinical_notes": "Patient stable, continue monitoring"
}
```

#### Analytics & Reporting
```
GET /api/v2/tenants/{tenantId}/reports/transactions
       ├─ Params: date_range, currency, status
       └─ Response: { total_volume, success_rate, fraud_rate, avg_latency }

GET /api/v2/tenants/{tenantId}/reports/fraud-patterns
       ├─ Identify fraud trends
       ├─ Params: date_range, limit
       └─ Response: { patterns: [], emerging_threats: [] }

GET /api/v2/tenants/{tenantId}/compliance/audit-log
       ├─ Compliance audit trail
       ├─ Params: user_id, action, date_range
       └─ Response: { events: [], total }
```

### Error Handling

All errors follow JSON:API format:

```json
{
  "errors": [
    {
      "status": 422,
      "code": "INVALID_AMOUNT",
      "title": "Validation Error",
      "detail": "Transaction amount must be positive",
      "source": {
        "pointer": "/data/attributes/amount"
      },
      "meta": {
        "timestamp": "2026-02-18T14:30:00Z",
        "request_id": "REQ-UUID-123"
      }
    }
  ]
}
```

### Rate Limiting

```
X-RateLimit-Limit: 10000
X-RateLimit-Remaining: 9999
X-RateLimit-Reset: 1645177200

# Tiers:
- Free: 1,000 requests/hour
- Starter: 100,000 requests/day
- Professional: 1M requests/day
- Enterprise: Custom
```

---

## GraphQL API

### Design Benefits
- Client specifies exact fields needed
- Single round-trip for complex data
- Better performance for mobile/bandwidth-limited
- Rich developer experience

### Base URL
```
POST https://api.golden-platform.example/graphql?tenantId={tenantId}
```

### Schema

```graphql
type Query {
  # Fintech queries
  transaction(id: ID!): Transaction
  transactions(filter: TransactionFilter, limit: Int = 100): [Transaction!]!
  transactionStats(dateRange: DateRange!): TransactionStats!
  
  # Healthcare queries
  patient(id: ID!): Patient
  patients(filter: PatientFilter): [Patient!]!
  patientAlerts(patientId: ID!, severity: [AlertSeverity]): [Alert!]!
  
  # Analytics
  report(type: ReportType!, dateRange: DateRange!): Report!
}

type Mutation {
  # Financial
  processTransaction(input: ProcessTransactionInput!): Transaction!
  reverseTransaction(transactionId: ID!): Transaction!
  
  # Healthcare
  admitPatient(input: AdmitPatientInput!): Patient!
  recordVitals(input: RecordVitalsInput!): VitalRecord!
  submitClinicalDecision(input: ClinicalDecisionInput!): DecisionResult!
}

type Subscription {
  # Real-time updates
  transactionUpdated(filter: TransactionFilter): Transaction!
  patientAlertTriggered(patientId: ID!): Alert!
}

# Fintech Types
type Transaction {
  id: ID!
  status: TransactionStatus!
  amount: Decimal!
  currency: String!
  sourceAccount: Account!
  destinationAccount: Account!
  fraudScore: Float!
  fraudDecision: FraudDecision!
  confidence: Float!
  settlementTime: DateTime
  createdAt: DateTime!
  audit: AuditInfo!
}

# Healthcare Types
type Patient {
  id: ID!
  mrn: String!
  name: String!
  dateOfBirth: Date!
  demographics: Demographics!
  medicalHistory: MedicalHistory!
  currentMedications: [Medication!]!
  allergies: [String!]!
}

type Alert {
  id: ID!
  patientId: ID!
  severity: AlertSeverity!
  message: String!
  detectedBy: String!
  confidence: Float!
  detectedAt: DateTime!
  acknowledgedAt: DateTime
  acknowledgedBy: String
}
```

### Example Query

```graphql
query GetPatientWithAlerts($patientId: ID!, $tenantId: ID!) {
  patient(id: $patientId) {
    id
    name
    dateOfBirth
    medicalHistory {
      conditions
      surgeries
    }
    currentMedications {
      name
      dosage
      frequency
    }
    alerts: patientAlerts(severity: [HIGH, CRITICAL]) {
      id
      severity
      message
      detectedAt
      confidence
    }
  }
}

# Variables
{
  "patientId": "P-2026-001",
  "tenantId": "hospital-a"
}

# Response
{
  "data": {
    "patient": {
      "id": "P-2026-001",
      "name": "John Doe",
      "dateOfBirth": "1975-06-15",
      "medicalHistory": {
        "conditions": ["Diabetes", "Hypertension"],
        "surgeries": ["Appendectomy 2015"]
      },
      "currentMedications": [
        {
          "name": "Metformin",
          "dosage": "1000mg",
          "frequency": "twice daily"
        }
      ],
      "alerts": [
        {
          "id": "ALT-001",
          "severity": "HIGH",
          "message": "Blood pressure elevated",
          "detectedAt": "2026-02-18T14:30:00Z",
          "confidence": 0.85
        }
      ]
    }
  }
}
```

---

## gRPC API (High-Performance)

### Benefits
- Binary protocol (3-5x faster than JSON)
- HTTP/2 multiplexing
- Streaming support
- Strong typing (Protocol Buffers)

### Usage
- High-frequency trading
- Real-time patient monitoring
- Service-to-service communication

### Protocol Definition

```protobuf
syntax = "proto3";

package golden.v2;

service TransactionService {
  rpc ProcessTransaction(ProcessTransactionRequest) returns (Transaction);
  rpc GetTransaction(GetTransactionRequest) returns (Transaction);
  rpc ListTransactions(ListTransactionsRequest) returns (stream Transaction);
  rpc SubscribeTransactionUpdates(SubscribeRequest) returns (stream TransactionUpdate);
}

message ProcessTransactionRequest {
  string tenant_id = 1;
  double amount = 2;
  string currency = 3;
  string source_account = 4;
  string destination_account = 5;
  map<string, string> metadata = 6;
}

message Transaction {
  string id = 1;
  string status = 2;
  double amount = 3;
  string currency = 4;
  FraudAssessment fraud = 5;
  int64 settlement_time_ms = 6;
}
```

---

## SDK & Client Libraries

### Available SDKs
- Python: `pip install golden-sdk`
- JavaScript: `npm install @golden/sdk`
- Go: `go get github.com/here2serveu/golden-platform`
- Java: `implementation 'io.golden:golden-java:2.0.0'`
- C#: `dotnet add package Golden.Platform`

### Quick Example (Python)

```python
from golden.sdk import GoldenClient
from golden.sdk.fintech import TransactionProcessor

# Initialize client
client = GoldenClient(
    tenant_id="acme-bank",
    api_key="sk_live_...",
    api_url="https://api.golden-platform.example"
)

# Process transaction
result = client.transactions.process(
    amount=1000.00,
    currency="USD",
    source_account="ACC-12345",
    destination_account="ACC-67890"
)

print(f"Transaction: {result.id}")
print(f"Fraud Decision: {result.fraud_decision}")
print(f"Confidence: {result.confidence}")
```

---

## API Versioning

Golden Platform commits to API stability:

```
v2 - Current (2024-present)
├─ Backward compatible for 3+ years
├─ Deprecation notice: 1 year warning
└─ Sunset: v2 supported until 2027

v3 - Planned (2027+)
└─ Will support v2 in parallel (2+ years)
```

---

## References

- [REST API - OpenAPI 3.1 Spec](openapi.yaml)
- [GraphQL Schema](schema.graphql)
- [gRPC Services](services.proto)
- [SDK Documentation](https://sdk.golden-platform.example)

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
