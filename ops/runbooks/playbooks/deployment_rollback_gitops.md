# Deployment Rollback with GitOps for Golden Platform

## Principles
* Rollbacks must be executed by reverting the Git commit or applying a known-good Helm chart tag.
* Direct manual changes (`kubectl edit` or `kubectl apply`) to production resources are strictly forbidden.
* The Git repository is the single source of truth for the desired state.

## Steps

1. **Identify Bad Change & Impact**
* Determine the specific commit, PR, or Helm chart value change that introduced the issue.
* Correlate the change with a failure in **SLOs**, Liveness/Readiness probes, or high error rates.
* Review ArgoCD/Flux events for the failing application (e.g., Backstage chart).

2. **Execute Git Revert**
* Use `git revert <commit-id>` or switch the GitOps target to a previous, known-good tag/commit.
* **Ensure the reverted state includes working Helm chart values.**

3. **Push to Main/Target Branch**
* Create and merge the rollback PR quickly (following the P1/P2 communication protocol).

4. **Observe Reconciliation & Stabilization**
* ArgoCD/Flux will automatically detect the Git change and:
    * Apply the previous stable manifests (e.g., older Helm chart version).
    * Restore the working application version.
* **Monitor Kubernetes resources** (Deployment/StatefulSet) to ensure old pods terminate and new stable pods become **Ready**.
* **Verify Application Health** by checking the `/healthcheck` endpoint for Backstage or core T2S microservices.

5. **Post-Rollback**
* Document the root cause analysis, including the time-to-revert (TTR).
* Update the incident ticket with the successful rollback outcome.
* Create a follow-up task to address the root cause and prevent recurrence.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
