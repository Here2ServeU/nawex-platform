# Platform Smoke Scenario

## Goal
Validate that core Golden Platform services can start and respond to health checks.

## Steps
1. Run `make up`.
2. Verify endpoints:
   - `http://localhost:8080/health` (app)
   - `http://localhost:8090/health` (transaction engine)
   - `http://localhost:8091/health` (fraud detector)
   - `http://localhost:8093/health` (EHR ingestion)
3. Execute `scripts/tools/healthcheck.sh`.
4. Confirm no failing checks.

## Exit Criteria
- All required endpoints return HTTP 200.
- Healthcheck script reports all green.
