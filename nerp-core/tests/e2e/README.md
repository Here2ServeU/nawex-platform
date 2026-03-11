# End-to-End Tests

Scope: full platform workflows against running services.

Scenarios:
- `scenarios/platform-smoke.md`

Recommended flow:
1. Start platform: `scripts/start_platform.sh`
2. Execute health checks: `scripts/healthcheck.sh`
3. Run scenario validations and capture evidence.

Use this directory for black-box, production-like validation.
