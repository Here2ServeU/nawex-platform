# golden-client-portal

Executive demo console: an Express + WebSocket service that streams **simulated** AI-ops insights to a vanilla-JS dashboard. Four verticals (healthcare, fintech, AI infrastructure / GPU fleet, VMware → OpenShift migration) cycle through `normal → degrading → alert → recovering` phases to tell a demo story. An AI-safety panel mirrors the shape of the Python platform's guardrails (autonomy mode, hourly action cap, kill switch). The data is simulated, and this service enforces nothing.

## Run

```bash
npm ci
npm start            # http://localhost:3001
npm run dev          # restart on file change (node --watch)
```

Docker:

```bash
docker build -t ghcr.io/here2serveu/golden-client-portal:dev .
docker run --rm -p 3001:3001 ghcr.io/here2serveu/golden-client-portal:dev
```

## Test & lint

```bash
npm test             # node --test (ephemeral ports, no external deps)
npm run lint         # ESLint 9 flat config
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `3001` | HTTP/WebSocket port |
| `HOST` | `0.0.0.0` | Bind address |
| `PLATFORM_NAME` | `Golden Platform` | Display name shown in the UI (served via `/api/config`) |
| `TICK_MS` | `3000` | Simulator tick interval |
| `AUTONOMY_MODE` | `supervised` | Simulated mode: `dry_run`, `supervised` or `autonomous` |
| `ACTION_CAP_PER_HOUR` | `20` | Simulated hourly action cap (the kill switch engages at the cap) |
| `WS_MAX_CONNECTIONS` | `100` | Concurrent `/feed` connections. Upgrades over the cap get HTTP 503 |
| `WS_MAX_PAYLOAD_BYTES` | `4096` | Max inbound WebSocket message size. Larger messages close the socket with code 1009 |
| `WS_ALLOWED_ORIGINS` | _(empty)_ | Comma-separated extra Origins allowed on `/feed`. Same-host origins are always allowed |
| `SHUTDOWN_TIMEOUT_MS` | `10000` | Grace period on SIGTERM/SIGINT before connections are forced closed |

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | `{status, service, version}` |
| GET | `/metrics` | Prometheus text: default Node metrics, `http_request_duration_seconds`, and `golden_client_portal_ws_*` |
| GET | `/` | Dashboard (static `public/`) |
| GET | `/api/config` | UI config: `platformName`, `consoleTitle`, vertical labels |
| GET | `/api/health` | Legacy detailed health (uptime, current vertical/phase) |
| GET | `/api/vertical` | Current vertical and the whitelist |
| POST | `/api/vertical` | `{"vertical": "healthcare" \| "fintech" \| "gpu" \| "migration"}`. Any other value returns 400 |
| GET | `/api/metrics/:vertical` | Live simulated metrics for a vertical |
| GET | `/api/alerts/:vertical` | Recent simulated alerts for a vertical |
| GET | `/api/roi/:vertical` | ROI case and breakdown |
| GET | `/api/safety` | Simulated guardrail state |
| GET | `/api/research/provenance` | Model provenance cards |
| WS | `/feed` | Pushes a `state_update` payload every tick. Accepts `{"type":"set_vertical","vertical":…}` (whitelisted) and `{"type":"ping"}` |

The `:vertical` routes return 400 for values outside the whitelist.

## Security notes

- The Helmet CSP allows only `cdn.jsdelivr.net` (Chart.js, pinned with SRI), `fonts.googleapis.com` and `fonts.gstatic.com`. It has no inline scripts or inline event handlers.
- JSON bodies are limited to 4 KB. WebSocket messages, connections and Origins are capped as described above.
- The image runs as non-root UID 10001.
