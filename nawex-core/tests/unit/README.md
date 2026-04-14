# Unit Tests

Scope: single-service behavior with no external network dependencies.

Current suites:
- `test_transaction_engine_unit.py`
- `test_ehr_ingestion_unit.py`

Run examples:

```bash
python -m unittest tests.unit.test_transaction_engine_unit
python -m unittest tests.unit.test_ehr_ingestion_unit
```

Guidelines:
- Keep tests deterministic and fast.
- Prefer Flask `test_client()` over real HTTP calls.
- Use fixture payloads from `tests/shared/fixtures` when possible.
