# SOC 2–Aligned GitOps Controls

This repository is intentionally structured to support **SOC 2, ISO 27001, and general auditability** using GitOps.

## 1. Change Management

- All changes to production infrastructure and applications are:
  - Proposed as Pull Requests
  - Reviewed and approved before merge
  - Logged with:
    - Author
    - Timestamp
    - Diff
    - Associated ticket / work item

This provides a **blame-free, fully traceable change history**.

## 2. Least Privilege & Separation of Duties

- ArgoCD / Flux controllers have:
  - Service accounts with scoped RBAC permissions.
  - Write access to cluster resources
  - Read-only access to the Git repository
- Engineers interact with the cluster mostly through Git, not via direct admin access.

## 3. Audit Logging

- Every change is visible in:
  - Git history (who/what/when/why)
  - ArgoCD or Flux reconcile logs/events
- Rollbacks are simple:
  - Revert PRs
  - Controllers reconcile the previous known-good state.

## 4. Configuration as Code

- Application + platform config is stored under:
  - `/helm` – Helm charts
  - `/gitops` – GitOps orchestration (ArgoCD + Flux)
- No manual, undocumented changes to production are required.

## 5. Demonstrating to Auditors

When talking to auditors or enterprise clients, you can show:

- Git log + PR reviews for specific changes
- ArgoCD Application history / Flux Kustomization events
- Evidence that:
  - No change goes live without a commit
  - Drift is auto-corrected back to the Git source of truth
