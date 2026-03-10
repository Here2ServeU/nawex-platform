# Structure Migration Guide

This repository now includes the canonical NERP scaffold alongside existing implementation paths.

## Current strategy
- Preserve existing operational paths to avoid breaking scripts and runtime behavior.
- Introduce canonical folders for long-term consistency and onboarding.
- Gradually move active content into canonical paths in follow-up PRs.

## Legacy to canonical mapping
- `terraform/` -> `infra/terraform/`
- `k8s/` + `openshift/` + top-level `helm/` -> `infra/kubernetes/` and `infra/helm/`
- `docs/architecture/`, `docs/compliance/`, `docs/guides/` -> `docs/02-architecture/`, `docs/03-compliance/`, `docs/05-operations/`
- `ops/playbooks/`, `ops/on-call/`, `ops/checklists/` -> `docs/05-operations/` and `sre/`
- `tools/` observability assets -> `observability/`

## Next migration phases
1. Update CI/CD and scripts to reference canonical paths.
2. Move selected source/docs content from legacy paths into canonical folders.
3. Keep compatibility shims until all references are updated.
4. Remove legacy duplicates once verified in CI.

## Phase Status

### Phase 1 (completed in this PR)
- Canonical docs populated from legacy sources:
	- `docs/architecture/*` -> `docs/02-architecture/*`
	- `docs/compliance/*` -> `docs/03-compliance/*`
	- `docs/guides/*` and `ops/*` operational docs -> `docs/05-operations/*`
- Canonical infra folders populated from legacy sources:
	- `terraform/modules/*` -> `infra/terraform/modules/*`
	- `terraform/live/*` -> `infra/terraform/global/live/*`
	- `k8s/*` -> `infra/kubernetes/base/*`
	- `helm/*` -> `infra/helm/*`
- Scripts and workflows updated to use canonical-first path resolution with temporary legacy fallbacks.

### Phase 2 (next PR)
- Move active service code into canonical app/domain folders and update import/runtime paths.
- Normalize docs links inside migrated files to canonical destinations.

### Phase 3 (next PR)
- Remove legacy path fallbacks after CI confirms all references are canonical.
