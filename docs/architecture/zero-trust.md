# NERP Security Architecture

## Zero-Trust Security Model

NERP implements a complete zero-trust architecture ensuring maximum protection for regulated industries (finance, healthcare).

**Core Principle:** "Never trust, always verify"

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ NERP Zero-Trust Model │
├─────────────────────────────────────────────────────────────────┤
│ │
│ External Request │
│ │ │
│ │
│ ┌──────────────────────┐ │
│ │ WAF / Rate Limit │ (DDoS protection, bot detection) │
│ └──────────┬───────────┘ │
│ │ │
│ │
│ ┌──────────────────────┐ │
│ │ API Gateway │ (TLS 1.3, mutual auth) │
│ │ (Kong/Traefik) │ │
│ └──────────┬───────────┘ │
│ │ │
│ │
│ ┌──────────────────────┐ │
│ │ Identity Provider │ (OAuth2, OIDC, FIDO2) │
│ │ (Keycloak/Auth0) │ │
│ └──────────┬───────────┘ │
│ │ │
│ │
│ ┌──────────────────────────────────────────┐ │
│ │ Policy Enforcement Point (PEP) │ │
│ │ ├─ OPA/Rego Rules Engine │ │
│ │ ├─ ABAC (Attribute-Based Access Control)│ │
│ │ └─ Context Enrichment │ │
│ └──────────┬───────────────────────────────┘ │
│ │ │
│ │
│ ┌──────────────────────────────────────────┐ │
│ │ Service-to-Service Security │ │
│ │ ├─ mTLS (mutual TLS) via Istio │ │
│ │ ├─ SPIFFE/SVID Identity │ │
│ │ └─ Encrypted Service Mesh │ │
│ └──────────┬───────────────────────────────┘ │
│ │ │
│ │
│ ┌──────────────────────────────────────────┐ │
│ │ Data Security Layer │ │
│ │ ├─ Field-Level Encryption (AES-256) │ │
│ │ ├─ Row-Level Security (PostgreSQL RLS) │ │
│ │ ├─ Vault Integration (Key Management) │ │
│ │ └─ Audit Logging (Immutable) │ │
│ └──────────────────────────────────────────┘ │
│ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Identity & Authentication

### OAuth2 + OpenID Connect

```yaml
# auth-config.yaml
auth:
  provider: keycloak
  realm: nerp-production
  
  oauth2:
    endpoints:
      authorization: https://auth.nerp-platform.io/auth/authorize
      token: https://auth.nerp-platform.io/auth/token
      introspect: https://auth.nerp-platform.io/auth/introspect
    
    scopes:
      - "openid profile email"
      - "nerp:read"
      - "nerp:write:transactions"
      - "nerp:write:admin"
  
  oidc:
    dynamic_client_registration: true
    discovery_endpoint: https://auth.nerp-platform.io/.well-known/openid-configuration
```

### Multi-Factor Authentication (MFA)

```python
# Python: mfa_enforcement.py
class MFAEnforcer:
    def __init__(self, vault_client):
        self.vault = vault_client
    
    def enforce_mfa(self, user_id: str, requested_at: str) -> bool:
        """
        Multi-factor authentication enforcement rules:
        - All admin operations: REQUIRED
        - Transaction >$100k: REQUIRED
        - First-time user: REQUIRED
        - New location: REQUIRED
        - Unusual time pattern: OPTIONAL (TOTP/SMS)
        """
        rules = [
            self._is_admin_operation(),
            self._is_high_value_transaction(),
            self._is_new_user_or_location(),
            self._is_unusual_time_pattern()
        ]
        
        required_mfa = any(rules)
        if required_mfa:
            return self._send_mfa_challenge(user_id)
        return True
    
    def _send_mfa_challenge(self, user_id: str) -> bool:
        """Support: TOTP, SMS, Email, Hardware tokens"""
        methods = self.vault.get_mfa_methods(user_id)
        return self._prompt_user_verification(methods)
```

### Passwordless Authentication

```bash
# FIDO2 WebAuthn support
curl -X POST https://auth.nerp-platform.io/auth/webauthn/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "engineer@company.com",
    "display_name": "Alice Engineer",
    "authenticator_selection": {
      "authenticator_attachment": "cross-platform",
      "resident_key": "required"
    }
  }'
```

---

## 2. Attribute-Based Access Control (ABAC)

### OPA/Rego Policy Engine

```rego
# policies/transaction_policy.rego
package nerp.fintech.transactions

import data.vault.encryption_keys
import data.audit.transaction_log

# Default: DENY (principle of least privilege)
default allow = false

# Rule 1: Allow transaction processing for authorized service accounts
allow {
    input.subject.type == "service_account"
    input.subject.roles contains "fintech-processor"
    input.tenant_id == input.subject.tenant_id
    input.action == "process_transaction"
    is_within_sla(input.timestamp)
}

# Rule 2: Allow transaction approval only for compliance team
allow {
    input.subject.type == "user"
    input.subject.roles contains "compliance-reviewer"
    input.action == "approve_transaction"
    is_transaction_flagged(input.transaction_id)
    has_valid_mfa(input.subject.id)
}

# Rule 3: Allow transaction reversal with audit trail
allow {
    input.subject.roles contains "finance-admin"
    input.action == "reverse_transaction"
    transaction_not_settled(input.transaction_id)
    time.now_ns() - transaction_created_time < 86400000000000 # 24 hours
}

# Rule 4: Deny high-value transactions outside business hours
deny["high_value_after_hours"] {
    input.action == "process_transaction"
    input.amount > 1000000
    not_within_business_hours()
}

# Deny transactions with insufficient compliance review
deny["compliance_not_approved"] {
    input.action == "process_transaction"
    input.amount > 500000
    not input.compliance.approved
}

# Helper functions
is_within_sla(timestamp) {
    time.now_ns() - timestamp < 86400000000000 # Within 24 hours
}

is_transaction_flagged(transaction_id) {
    transaction_log[transaction_id].fraud_score > 0.7
}

has_valid_mfa(user_id) {
    audit.mfa_verified[user_id]
    audit.mfa_timestamp[user_id] > time.now_ns() - 3600000000000 # Last 1 hour
}

transaction_not_settled(transaction_id) {
    transaction_log[transaction_id].status != "SETTLED"
}

not_within_business_hours {
    hour := time.now_ns() / 3600000000000 % 24
    hour < 9 # Before 9 AM
}
```

### Healthcare HIPAA Policies

```rego
# policies/hipaa_policy.rego
package nerp.healthcare.hipaa

import data.vault.encryption_keys

# All healthcare data access requires audit logging
default allow = false

allow {
    input.action == "read_patient_record"
    input.subject.roles contains "healthcare-worker"
    patient_in_facility(input.patient_id, input.subject.facility_id)
    has_valid_credentials(input.subject.id)
    is_medically_necessary(input.subject.id, input.patient_id)
}

# Restrict access to minimum necessary information
allow {
    input.action == "read_patient_vitals"
    input.subject.roles contains "nursing"
    input.fields contains "heart_rate"
    input.fields contains "blood_pressure"
    not input.fields contains "psychiatric_history" # Not needed for nursing
    not input.fields contains "genetic_markers" # Not needed for nursing
}

# Audit every access
audit_required {
    input.action == "read_patient_record"
    input.resource.classification in ["PHI", "SENSITIVE", "GENETIC"]
}

# Encryption in transit (TLS 1.3 minimum)
allow {
    input.transport.protocol == "TLS"
    input.transport.version == "1.3"
}

deny["unencrypted_transmission"] {
    input.transport.protocol != "TLS"
    input.resource.classification contains "PHI"
}
```

---

## 3. Service-to-Service Security (mTLS)

### Istio Configuration

```yaml
# istio-config.yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: nerp-production
spec:
  mtls:
    mode: STRICT # Require mTLS for all service-to-service
  portLevelMtls:
    "8080":
      mode: STRICT

---
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: service-mesh-authz
  namespace: nerp-production
spec:
  selector:
    matchLabels:
      app: fintech-processor
  action: ALLOW
  rules:
  - from:
    - source:
        principals:
        - "cluster.local/ns/nerp-production/sa/transaction-validator"
        - "cluster.local/ns/nerp-production/sa/fraud-detector"
    to:
    - operation:
        methods:
        - POST
        paths:
        - "/api/v2/process"

---
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: jwt-auth
  namespace: nerp-production
spec:
  jwtRules:
  - issuer: "https://auth.nerp-platform.io"
    jwksUri: "https://auth.nerp-platform.io/.well-known/jwks.json"
    audiences:
    - "nerp-services"
```

### SPIFFE/SVID Identity

```bash
# All services get cryptographic identity from SPIFFE
# Identity format: spiffe://nerp-platform.io/services/fintech-processor

# Spire agent on each node:
spire-agent API socket: /tmp/spire-agent/public/api.sock

# Service fetches its identity certificate:
curl --unix-socket /tmp/spire-agent/public/api.sock \
  spiffe://local/api/fetch-svid
```

---

## 4. Secrets Management (HashiCorp Vault)

### Vault Architecture

```yaml
# vault-config.yaml
vault:
  mode: ha-cluster # 3 nodes minimum
  storage: postgresql
  encryption: transit-engine
  
  auth_methods:
    - type: kubernetes
      path: kubernetes
      config:
        kubernetes_host: https://kubernetes.default.svc
        kubernetes_ca_cert: |
          -----BEGIN CERTIFICATE-----
          ...
    
    - type: jwt
      path: oauth2
      config:
        oidc_discovery_url: https://auth.nerp-platform.io
        bound_audiences: vault
    
    - type: approle
      path: approle
  
  secrets_engines:
    - path: secret/
      type: kv
      version: 2
      config:
        max_lease_ttl: 2592000 # 30 days
    
    - path: transit/
      type: transit
      config:
        key_derivation: true
        convergent_encryption: false
    
    - path: pki/
      type: pki
      config:
        ttl: 8760h
        max_lease_ttl: 87600h
    
    - path: database/
      type: database
      config:
        postgresql:
          connection_url: "postgresql://vault:password@postgres:5432/vault"
          allowed_roles:
            - readonly
            - readwrite
```

### Encryption in Transit (Transit Secrets Engine)

```python
# Python: encryption.py
import hvac

class VaultEncryption:
    def __init__(self, vault_client, tenant_id: str):
        self.client = vault_client
        self.tenant_id = tenant_id
    
    def encrypt_field(self, plaintext: str, field_path: str) -> str:
        """
        Encrypt sensitive fields (PII, PHI, financial data)
        
        Vault derives unique key per field path and tenant
        """
        response = self.client.secrets.transit.encrypt_data(
            mount_point="transit",
            name=f"nerp-{self.tenant_id}-{field_path}",
            plaintext=plaintext
        )
        return response["data"]["ciphertext"]
    
    def decrypt_field(self, ciphertext: str, field_path: str) -> str:
        """Decrypt encrypted field"""
        response = self.client.secrets.transit.decrypt_data(
            mount_point="transit",
            name=f"nerp-{self.tenant_id}-{field_path}",
            ciphertext=ciphertext
        )
        return response["data"]["plaintext"]
    
    def rotate_encryption_keys(self) -> bool:
        """Key rotation every 90 days (automatic)"""
        response = self.client.secrets.transit.rotate_key(
            mount_point="transit",
            name=f"nerp-{self.tenant_id}-master"
        )
        return response["auth"]["lease_duration"] > 0

# Usage example
vault = hvac.Client(url="https://vault.nerp-platform.io", token=token)
enc = VaultEncryption(vault, tenant_id="acme-bank")

# Encrypt customer SSN
encrypted_ssn = enc.encrypt_field("123-45-6789", "/customers/ssn")

# Decrypt when needed
plain_ssn = enc.decrypt_field(encrypted_ssn, "/customers/ssn")
```

### Database User Provisioning

```python
# vault_db_user.py
# Vault automatically creates/revokes database users

vault_response = vault_client.auth.kubernetes.login(
    role="fintech-processor",
)

# Request database credentials
db_creds = vault_client.secrets.database.generate_credentials(
    name="fintech-readonly",
    mount_point="database"
)

# Response includes:
# {
# "username": "v-fintech-abc123-xyz", # Auto-generated
# "password": "SecureRandomPassword", # Vault-generated
# "ttl": "1h" # Auto-revokes after 1 hour
# }

# Use credentials
import psycopg2
conn = psycopg2.connect(
    host="postgres.nerp-platform.io",
    user=db_creds["data"]["username"],
    password=db_creds["data"]["password"],
    database="nerp_fintech"
)
```

---

## 5. Data Security

### Field-Level Encryption (at rest)

```sql
-- PostgreSQL with Vault transit engine
CREATE TABLE transactions (
    id UUID PRIMARY KEY,
    amount DECIMAL(15,2), -- Unencrypted (logged)
    encrypted_account_number BYTEA, -- Encrypted with Vault
    encrypted_routing_number BYTEA, -- Encrypted with Vault
    fraud_score FLOAT, -- Unencrypted (analysis)
    encrypted_customer_id BYTEA, -- HIPAA/PCI-DSS requirement
    created_at TIMESTAMP,
    tenant_id UUID
);

-- Row Level Security (multi-tenant isolation)
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY transactions_tenant_isolation ON transactions
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Encrypted column trigger (automatic)
CREATE FUNCTION encrypt_before_insert()
RETURNS TRIGGER AS $$
BEGIN
    -- Vault handles encryption remotely (TLS 1.3)
    NEW.encrypted_account_number := vault_encrypt(
        'transit/nerp-' || current_setting('app.current_tenant_id') || '-account',
        NEW.encrypted_account_number
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER encrypt_transaction_trigger
BEFORE INSERT ON transactions
FOR EACH ROW EXECUTE FUNCTION encrypt_before_insert();
```

### Row-Level Security (RLS)

```python
# postgres_rls.py
class PostgresRLS:
    def __init__(self, connection, tenant_id: str):
        self.conn = connection
        self.tenant_id = tenant_id
    
    def set_tenant_context(self):
        """Set Postgres session variable for RLS"""
        cursor = self.conn.cursor()
        cursor.execute(
            f"SET app.current_tenant_id = '{self.tenant_id}';"
        )
        cursor.close()
    
    def create_tenant_policies(self):
        """Create RLS policies for new tenant"""
        cursor = self.conn.cursor()
        
        # Create schema for tenant
        cursor.execute(f"CREATE SCHEMA tenant_{self.tenant_id};")
        
        # Create tables with RLS enabled
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS tenant_{self.tenant_id}.transactions (
                id UUID PRIMARY KEY,
                tenant_id UUID NOT NULL,
                amount DECIMAL(15,2),
                created_at TIMESTAMP
            );
            
            ALTER TABLE tenant_{self.tenant_id}.transactions
            ENABLE ROW LEVEL SECURITY;
            
            CREATE POLICY tenant_isolation ON tenant_{self.tenant_id}.transactions
                USING (tenant_id = '{self.tenant_id}')
                WITH CHECK (tenant_id = '{self.tenant_id}');
        """)
        
        self.conn.commit()
        cursor.close()
```

---

## 6. Audit & Compliance Logging

### Immutable Audit Log

```python
# audit_logger.py
class ImmutableAuditLog:
    def __init__(self, vault_client, kafka_producer):
        self.vault = vault_client
        self.kafka = kafka_producer
        self.retention_years = 7 # Compliance requirement
    
    def log_event(self, event: dict) -> str:
        """
        Immutable audit logging:
        1. Write to Kafka (distributed log)
        2. Hash to blockchain (optional: Confidential Ledger)
        3. Archive to cold storage (S3/Azure Blob)
        """
        # Add metadata
        event['timestamp'] = datetime.utcnow().isoformat()
        event['hash'] = self._compute_hash(event)
        event['sequence'] = self._get_sequence_number()
        
        # Write to Kafka (immutable topic, retention = 7 years)
        self.kafka.send(
            topic=f"audit-{event['tenant_id']}",
            value=json.dumps(event),
            key=event['tenant_id']
        )
        
        # Optional: Write to Azure Confidential Ledger
        if event['classification'] == 'REGULATORY':
            self.vault.write(
                path="ledger/append",
                body=event
            )
        
        return event['hash']
    
    def _compute_hash(self, event: dict) -> str:
        """Compute SHA-256 hash for integrity verification"""
        import hashlib
        return hashlib.sha256(
            json.dumps(event, sort_keys=True).encode()
        ).hexdigest()

# Example: Transaction audit
audit_log = ImmutableAuditLog(vault_client, kafka_producer)

audit_log.log_event({
    'action': 'transaction_processed',
    'transaction_id': 'TXN-001',
    'actor': 'service-account-fintech',
    'actor_ip': '10.0.0.5',
    'result': 'SUCCESS',
    'amount': 10000.00,
    'classification': 'REGULATORY',
    'tenant_id': 'acme-bank'
})
```

---

## Compliance Checklist

- PCI-DSS 3.2.1 (financial data encryption, mTLS, audit logging)
- HIPAA BAA (PHI encryption, access controls, audit trail)
- SOC 2 Type II (control effectiveness, logging, incident response)
- GDPR (data minimization, right to deletion, consent tracking)
- ISO 27001 (information security management system)

---

## References

- [OPA Policy Examples](../../gitops/policies/)
- [Compliance Documentation](../compliance/)

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
