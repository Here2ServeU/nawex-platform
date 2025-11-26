# Deployment Rollback with GitOps

## Principles
- Never `kubectl edit` production.
- Rollbacks are Git commits, not manual hot-fixes.

## Steps

1. **Identify Bad Change**
   - Determine the commit/PR that introduced the issue.
   - Correlate with ArgoCD/Flux events.

2. **Revert Commit**
   - Use `git revert <commit>` or roll back to a previous tag/commit.

3. **Push to Main**
   - Once reviewed and approved, merge the rollback PR.

4. **Observe Reconciliation**
   - ArgoCD/Flux will:
     - Apply previous manifests.
     - Restore working version.

5. **Post-Rollback**
   - Document in incident ticket.
   - Create a follow-up task to address root cause.
