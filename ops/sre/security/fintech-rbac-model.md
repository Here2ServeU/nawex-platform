# Fintech RBAC Model: Role-Based Access Control for Financial Services

## Overview

This document extends the platform's [RBAC model](/ops/sre/security/reliability-rbac-model.md) with fintech-specific roles, permissions, and segregation of duties required by PCI-DSS, SOX, and GLBA compliance frameworks.

## Role Hierarchy

### Payment Operations Roles

| Role | Description | Scope | PCI-DSS Alignment |
| --- | --- | --- | --- |
| **Payment Admin** | Full access to payment gateway configuration, settlement controls, and transaction monitoring | `fintech` namespace | Req 7.1 - Restrict access to CHD |
| **Transaction Analyst** | Read-only access to transaction logs, fraud reports, and settlement status | `fintech` namespace (read) | Req 10 - Track & monitor access |
| **Fraud Investigator** | Access to fraud detection dashboards, flagged transactions, and manual review workflows | `fintech` namespace (fraud tools) | Req 12.10 - Incident response |
| **Compliance Officer** | Read-only access to all audit logs, compliance reports, and control evidence | All namespaces (read, audit) | Req 12.4 - Security responsibilities |
| **Settlement Operator** | Trigger and monitor settlement batches; view reconciliation reports | `fintech` namespace (settlement) | SOX - Segregation of duties |

### Segregation of Duties Matrix

| Action | Payment Admin | Txn Analyst | Fraud Investigator | Compliance Officer | Settlement Operator |
| --- | --- | --- | --- | --- | --- |
| Configure payment gateway | | | | | |
| View transaction logs | | | | | |
| Block fraudulent transactions | | | | | |
| Trigger settlement | | | | | |
| Modify fraud thresholds | | | | | |
| View compliance reports | | | | | |
| Access cardholder data | | | | | |
| Deploy code changes | | | | | |
| Modify RBAC policies | | | | | |

### SOX-Required Controls

1. **No single person** can both initiate and approve a settlement batch.
2. **Developers** cannot access production cardholder data.
3. **Payment Admins** cannot modify their own access permissions.
4. All role assignments require **manager approval** and are reviewed quarterly.
5. **Privileged access** (Payment Admin, Settlement Operator) requires MFA and time-bound session tokens.

## Kubernetes RBAC Implementation

```yaml
# Example: Transaction Analyst role
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: fintech
  name: transaction-analyst
rules:
  - apiGroups: [""]
    resources: ["pods", "services"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["transaction-dashboard-config"]
    verbs: ["get"]
```

```yaml
# Example: Payment Admin role (restricted CDE access)
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: fintech
  name: payment-admin
rules:
  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets"]
    verbs: ["get", "list", "update", "patch"]
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["payment-gateway-config", "fraud-model-config"]
    verbs: ["get", "update"]
```

## Access Review Schedule

| Review Type | Frequency | Responsible | Regulatory Basis |
| --- | --- | --- | --- |
| User access certification | Quarterly | Compliance Officer | SOX §404, PCI-DSS Req 7 |
| Privileged access review | Monthly | Security Team | GLBA Safeguards Rule |
| Service account audit | Monthly | SRE Team | PCI-DSS Req 8.6 |
| RBAC policy drift check | Weekly (automated) | AI Platform | Continuous compliance |

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
