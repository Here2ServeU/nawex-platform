# Integration Tests

Scope: cross-service flows for fintech and healthcare domains.

Current suites:
- `test_fintech_flow.py`
- `test_healthcare_flow.py`

Run examples:

```bash
python -m unittest tests.integration.test_fintech_flow
python -m unittest tests.integration.test_healthcare_flow
```

Guidelines:
- Validate end-to-end payload handoff between services.
- Cover both happy-path and policy/validation behavior.
- Keep state isolated per test using test client setup.
