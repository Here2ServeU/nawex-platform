# golden-workload

Reference workload for the Golden Platform. It is an instrumented Express service that emits golden signals (latency, traffic, errors, saturation) and exposes **bounded** chaos endpoints. The AI-ops agents use it to test detection and remediation end to end.

## Run

```bash
npm ci
npm start            # http://localhost:8080
npm run dev          # restart on file change (node --watch)
```

Docker:

```bash
docker build -t ghcr.io/here2serveu/golden-workload:dev .
docker run --rm -p 8080:8080 ghcr.io/here2serveu/golden-workload:dev
```

## Test & lint

```bash
npm test             # node --test (ephemeral ports)
npm run lint         # ESLint 9 flat config
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8080` | HTTP port |
| `HOST` | `0.0.0.0` | Bind address |
| `CHAOS_ENABLED` | `true` | When `false`, `/chaos/*` returns 403 |
| `CHAOS_MAX_LATENCY_MS` | `10000` | Upper bound for `delay_ms` |
| `CHAOS_MAX_CPU_STRESS_MS` | `30000` | Upper bound for `duration_ms` of a CPU stress run |
| `CHAOS_MAX_MEMORY_LEAK_MB` | `256` | Total cap for the simulated memory leak |
| `SHUTDOWN_TIMEOUT_MS` | `10000` | Grace period on SIGTERM/SIGINT |

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | `{status, service, version}` (not affected by chaos) |
| GET | `/metrics` | Prometheus text: default Node metrics, `http_request_duration_seconds`, and `golden_workload_chaos_*` gauges |
| GET | `/metrics/json` | JSON golden signals for the Python ObserverAgent (see below) |
| GET | `/` | Service info (business route) |
| GET | `/api/users` | Sample data (business route) |
| POST | `/chaos/latency` | `{"delay_ms": 0..10000}` adds latency to business routes. The legacy key `delay` is also accepted, and `0` clears the injection |
| POST | `/chaos/errors` | `{"rate": 0..1}` sets the probability that a business request returns 500 |
| POST | `/chaos/error-spike` | `{"count": 1..1000}` (default 50) records synthetic 5xx samples in the window |
| POST | `/chaos/cpu` | `{"duration_ms": 100..30000, "workers": 1..cores}` burns CPU in worker threads, so the event loop stays responsive. Returns 202, or 409 if a run is already active |
| POST | `/chaos/memory` | `{"intensity": 1..10}` allocates 8 MB per unit up to the cap. Returns 409 once the cap is reached |
| GET | `/chaos/stress-test?intensity=1..10` | Legacy alias of `/chaos/memory` |
| POST | `/ops/heal` | Clears all chaos state (latency, errors, CPU workers, leak, signal window) |

Invalid input (wrong type, non-integer, or out of range) returns **400** with `{"error": "..."}`.

### `/metrics/json` contract

```json
{
  "timestamp": "2026-10-11T12:00:00.000Z",
  "service": "golden-workload",
  "window_seconds": 60,
  "metrics": {
    "latency_ms": 12,
    "error_rate": 0.0,
    "error_rate_percent": 0.0,
    "cpu_usage_percent": 4.2,
    "memory_usage_percent": 1.3,
    "memory_usage_mb": 61,
    "request_count": 40
  },
  "chaos_state": { "latency_injection_ms": 0, "error_injection_rate": 0, "cpu_stress_active": false, "cpu_stress_remaining_ms": 0, "leaked_mb": 0 }
}
```

- `latency_ms` is the mean latency of business requests over the last 60 s. If there was no business traffic in that window, it reports the currently injected latency.
- `error_rate` is the **percentage** (0–100) of 5xx responses in the window. `error_rate_percent` is an alias that matches the analyzer threshold key.
- `cpu_usage_percent` is the process CPU across all available cores. `memory_usage_percent` is RSS divided by the cgroup memory limit (or host memory if no limit is set).
