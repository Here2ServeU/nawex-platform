# NAWEX Structure Migration

This repository is aligned to a dual-track structure:

- Existing production modules remain intact for continuity.
- Canonical NAWEX platform structure is available for new development.

## Canonical Domains

- `platform/`
- `ai/`
- `decision_engine/`
- `automation/`
- `data_platform/`
- `api/`
- `frontend/`
- `infrastructure/`
- `security/`
- `compliance/`
- `datasets/`
- `models/`
- `experiments/`
- `demos/`
- `verticals/`
- `research/`
- `education/`

## Non-Breaking Policy

- Existing directories like `app/`, `infra/`, `fintech/`, and `healthcare/` are preserved.
- New work should target canonical paths where available.
- Legacy paths can be referenced from canonical modules during transition.

## Mapping Notes

- `infra/` -> `infrastructure/`
- `app/` -> `api/` and `frontend/`
- `fintech/` + `healthcare/` -> `verticals/fintech/` and `verticals/healthcare/`

Detailed service-level mapping: `docs/architecture/canonical-path-index.md`
