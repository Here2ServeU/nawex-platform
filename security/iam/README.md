# IAM Baseline

This folder defines identity and access management baselines for Golden platform services.

## Scope
- Human access model (admins, operators, auditors, developers).
- Workload/service account permissions (least privilege).
- Kubernetes namespace-level RBAC defaults.

## Files
- `least-privilege-matrix.md`: Role-to-capability mapping.
- `k8s-rbac-baseline.yaml`: Baseline Kubernetes RBAC objects.

## AWS workforce and workload identity
- `../identity/access-model.yaml`: AWS personas → IAM Identity Center permission sets → AD groups
  (SCIM-provisioned by PingFederate). This one file drives Terraform and `golden iam model`.
- Guardrails (SCPs/RCPs), the permission boundary and the Identity Center module are in
  `deploy/terraform/modules/aws/{org-guardrails,permission-boundary,identity-center}`.
- See `docs/modernization/aws-iam-modernization.md` for the control-placement model.

## Principles
- Deny by default.
- Separate duties for operations and approvals.
- Time-bound elevated access.
