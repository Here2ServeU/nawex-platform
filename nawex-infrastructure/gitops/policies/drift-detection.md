# Drift Detection with ArgoCD & FluxCD

This platform uses **GitOps** to detect and remediate drift between:
- Desired state in Git
- Actual state in the cluster(s)

## ArgoCD

- Each `Application` in `gitops/argocd` has:

  ```yaml
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
  ```

- **What this gives you:**
  - If someone changes a resource directly via `kubectl`, ArgoCD detects the diff and:
    - Flags it as **OutOfSync**
    - Auto-syncs back to Git (self-heal)
  - Any manual hot-fixes must go through Git, producing a clear, auditable history.

## FluxCD

- The `Kustomization` in `gitops/flux/kustomization-platform.yaml` runs every minute:

  ```yaml
  interval: 1m
  prune: true
  wait: true
  ```

- **What this gives you:**
  - Flux periodically compares live state against the manifests in Git.
  - Any drift is reconciled back to the desired state.
  - `prune: true` removes resources that were deleted in Git, avoiding config sprawl.

## How to Demo Drift Detection in Interviews

1. Show your ArgoCD UI or Flux events.
2. Manually edit a Deployment (e.g., scale replicas via `kubectl`).
3. Wait for reconciliation:
   - ArgoCD will mark the app as OutOfSync, then auto-sync.
   - Flux will show events indicating it reapplied the desired config.
4. Highlight how:
   - You treat the UI/CLI as *read-only*
   - Git + reviews are the single source of truth.

---

*Copyright (c) 2026 Nawex Platform (NAWEX). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
