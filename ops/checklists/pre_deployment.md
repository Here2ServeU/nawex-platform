# Pre-Deployment Checklist

- [ ] Change request / ticket approved.
- [ ] Code merged to main branch.
- [ ] CI pipeline green (tests, linting, security scans).
- [ ] Image scanned (Trivy/Snyk) and pushed to registry.
- [ ] Helm chart version bumped and committed.
- [ ] SLO impact reviewed; error budget available.
- [ ] Runbooks updated if new failure modes introduced.
- [ ] Rollback plan documented.
