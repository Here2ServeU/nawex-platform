# IAM Baseline

This folder defines identity and access management baselines for NAWEX services.

## Scope
- Human access model (admins, operators, auditors, developers).
- Workload/service account permissions (least privilege).
- Kubernetes namespace-level RBAC defaults.

## Files
- `least-privilege-matrix.md`: Role-to-capability mapping.
- `k8s-rbac-baseline.yaml`: Baseline Kubernetes RBAC objects.

## Principles
- Deny by default.
- Separate duties for operations and approvals.
- Time-bound elevated access.
