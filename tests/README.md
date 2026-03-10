# NERP Test Strategy

This directory contains the enterprise test framework for NERP.

## Structure

- `unit/`: fast, isolated service logic tests.
- `integration/`: cross-service domain flow tests.
- `e2e/`: full-platform scenario validation.
- `performance/`: load and latency tests.
- `security/`: API and policy hardening checks.
- `shared/`: fixtures and reusable test utilities.

## Quick Start

```bash
python -m unittest tests.unit.test_transaction_engine_unit
python -m unittest tests.integration.test_fintech_flow
```

## Coverage Priorities

- Fintech: transaction processing, fraud scoring, payment resilience.
- Healthcare: EHR ingestion, FHIR validation, PHI query behavior.
- Platform: startup smoke, health checks, latency under load.

## CI Recommendations

1. Run unit tests on every push.
2. Run integration tests on pull requests.
3. Run performance and security suites on schedule and release branches.
4. Publish test evidence and trend reports for SRE/compliance review.
