# Security Tests

Scope: API hardening checks, policy assertions, and secure defaults.

Current suites:
- `test_service_headers.py`

Run example:

```bash
python -m unittest tests.security.test_service_headers
```

Extend this suite with checks for:
- authentication and authorization behavior
- secret leakage prevention
- security header and transport requirements
