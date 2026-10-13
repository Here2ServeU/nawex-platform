# Canonical Path Index

This document defines the migration map from legacy Golden Platform paths to canonical Golden Platform domains.

## Usage Rules

- New development should prefer canonical paths.
- Existing production paths remain valid during transition.
- When touching legacy code, add or update a canonical counterpart when practical.

## Domain Mapping

| Legacy path | Canonical path | Notes |
| --- | --- | --- |
| `app/` | `api/` + `frontend/` | Backend and UI split into explicit platform domains. |
| `infra/` | `infrastructure/` | Canonical home for terraform, kubernetes, and helm assets. |
| `fintech/` | `verticals/fintech/` | Domain-specific reliability services. |
| `healthcare/` | `verticals/healthcare/` | Domain-specific clinical reliability services. |
| `docs/01-executive/` and similar numbered docs | `docs/executive/`, `docs/architecture/`, `docs/product/`, `docs/compliance/`, `docs/guides/` | Canonical docs taxonomy. |

## Fintech Service Mapping

| Legacy component | Canonical target |
| --- | --- |
| `src/golden/services/fintech/transaction_engine.py` | `verticals/fintech/` + `api/services/` integration |
| `src/golden/services/fintech/fraud_detector.py` | `verticals/fintech/fraud_detection.py` |
| `src/golden/services/fintech/payment_gateway.py` | `verticals/fintech/payment_gateway_monitor.py` |

## Healthcare Service Mapping

| Legacy component | Canonical target |
| --- | --- |
| `src/golden/services/healthcare/ehr_ingestion.py` | `verticals/healthcare/ehr_monitor.py` + `data_platform/` ingestion |
| `src/golden/services/healthcare/clinical_decision.py` | `decision_engine/` + `verticals/healthcare/` |
| `src/golden/services/healthcare/patient_gateway.py` | `verticals/healthcare/` + `api/services/` integration |

## Platform Core Mapping

| Legacy component | Canonical target |
| --- | --- |
| `platform/event_streams/` and `platform/kafka/` | `platform/event_bus/` + `data_platform/streaming/` |
| `platform/resilience_engine/` and `platform/rules-engine/` | `decision_engine/` |
| `platform/automation_engine/` | `automation/` |
| `platform/notification_system/` | `api/services/` and workflow notification hooks |
| `platform/telemetry/` | `platform/telemetry/` (canonical) |
| `platform/ingestion/` | `platform/ingestion/` + `data_platform/` |

## Implementation Priority

1. Route all new endpoints and orchestration to `api/`, `decision_engine/`, and `automation/`.
2. Migrate vertical business logic to `verticals/`.
3. Consolidate deployment assets in `infrastructure/`.
4. Keep compatibility wrappers in legacy paths until deprecation is approved.
