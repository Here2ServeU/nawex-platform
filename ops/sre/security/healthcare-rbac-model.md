# Healthcare RBAC Model: Role-Based Access Control for Clinical Systems

## Overview

This document extends the platform's [RBAC model](/ops/sre/security/reliability-rbac-model.md) with healthcare-specific roles, permissions, and segregation of duties required by HIPAA, HITECH, and FDA 21 CFR Part 11 compliance frameworks.

## Role Hierarchy

### Clinical Operations Roles

| Role | Description | Scope | HIPAA Alignment |
| --- | --- | --- | --- |
| **Clinical Admin** | Full access to EHR gateway configuration, clinical decision thresholds, and patient data routing | `healthcare` namespace | §164.308 Access Management |
| **Clinician** | Access to patient records within their department, clinical alerts, and decision support outputs | `healthcare` namespace (dept-scoped) | §164.312 Access Control |
| **PHI Auditor** | Read-only access to all PHI audit logs, access reports, and compliance dashboards | All namespaces (audit, read) | §164.312(b) Audit Controls |
| **HIPAA Privacy Officer** | Access to breach reports, consent records, and de-identification pipelines | All namespaces (compliance) | §164.530 Requirements |
| **Clinical Data Engineer** | Manage EHR ingestion pipelines, FHIR endpoint configuration, and data transformation rules | `healthcare` namespace (data ops) | §164.308 Workforce Security |

### Segregation of Duties Matrix

| Action | Clinical Admin | Clinician | PHI Auditor | Privacy Officer | Data Engineer |
| --- | --- | --- | --- | --- | --- |
| Configure EHR gateway | | | | | |
| View patient records | | (dept) | | | |
| Access PHI audit logs | | | | | |
| Manage consent records | | | | | |
| Modify clinical thresholds | | | | | |
| View compliance reports | | | | | |
| Access raw patient data | | (dept) | | | |
| Deploy code changes | | | | | |
| Modify RBAC policies | | | | | |
| Manage data pipelines | | | | | |
| Override quarantine | | (attending) | | | |

### HIPAA-Required Controls

1. **Minimum Necessary**: Users can only access PHI required for their job function (§164.502(b)).
2. **Workforce Clearance**: All personnel with PHI access undergo background checks and HIPAA training (§164.308(a)(3)).
3. **Emergency Access**: Break-glass procedures allow temporary elevated access with full audit logging (§164.312(a)(2)(ii)).
4. **Automatic Logoff**: Clinical sessions timeout after 15 minutes of inactivity (§164.312(a)(2)(iii)).
5. **Unique User Identification**: Every PHI access is tied to a unique, non-shared user identity (§164.312(a)(2)(i)).

## Kubernetes RBAC Implementation

```yaml
# Example: Clinician role (department-scoped)
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: healthcare
  name: clinician
rules:
  - apiGroups: [""]
    resources: ["pods", "services"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["clinical-dashboard-config"]
    verbs: ["get"]
```

```yaml
# Example: Clinical Admin role (HIPAA-restricted PHI access)
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: healthcare
  name: clinical-admin
rules:
  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets"]
    verbs: ["get", "list", "update", "patch"]
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["ehr-gateway-config", "clinical-model-config"]
    verbs: ["get", "update"]
```

## Access Review Schedule

| Review Type | Frequency | Responsible | Regulatory Basis |
| --- | --- | --- | --- |
| PHI access certification | Quarterly | HIPAA Privacy Officer | HIPAA §164.308(a)(4) |
| Privileged access review | Monthly | Security Team | HIPAA §164.312(a) |
| Service account audit | Monthly | SRE Team | FDA 21 CFR Part 11 |
| RBAC policy drift check | Weekly (automated) | AI Platform | Continuous compliance |
| Workforce termination access | Immediately | HR + Clinical Admin | HIPAA §164.308(a)(3)(ii)(C) |

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
