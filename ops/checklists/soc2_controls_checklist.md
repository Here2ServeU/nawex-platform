# SOC 2 Controls Checklist (Deployment Focus)

- [ ] All changes traceable to a ticket or work item.
- [ ] At least one peer review before merge.
- [ ] Git history preserved (no force pushes to main).
- [ ] CI pipeline includes:
  - [ ] Static code analysis
  - [ ] Dependency vulnerability scan
  - [ ] Container image scan
- [ ] GitOps tool logs (ArgoCD/Flux) retained for audit period.
- [ ] Access to production cluster restricted to GitOps service accounts + break-glass.
