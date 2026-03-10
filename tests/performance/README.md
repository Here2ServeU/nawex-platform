# Performance Tests

Scope: load and latency validation for critical APIs.

Current assets:
- `k6/transaction-load.js`

Run example:

```bash
k6 run tests/performance/k6/transaction-load.js
```

Optional base URL override:

```bash
BASE_URL=http://localhost:8090 k6 run tests/performance/k6/transaction-load.js
```

Suggested thresholds:
- p95 latency under 400ms
- error rate under 2%
