# AI Safety & Security Model

The platform runs machine-learning models on regulated data (PHI, cardholder data,
infrastructure telemetry) and can take **autonomous remediation actions** against
production systems — restarting services, failing over gateways, draining GPU nodes,
cutting over migrated VMs. This document is the security model for that capability:
what can go wrong, and which control in `golden.security` stops it.

Design principles:

1. **Safe by default.** Out of the box the platform only *recommends*
   (`GOLDEN_AUTONOMY_MODE=dry_run`). Acting is an explicit opt-in.
2. **Every action passes one gate.** The action governor (`golden/security/actions.py`)
   is the only path from a model decision to a side effect.
3. **Fail closed.** Unknown actions are denied, invalid inputs are rejected, an
   unparseable autonomy mode falls back to `dry_run`, a tampered model refuses to load.
4. **Everything is evidence.** Verdicts, approvals and rejections go to a
   hash-chained audit log and to Prometheus.

## Threat model

| # | Threat | Example | Impact | Primary controls |
|---|---|---|---|---|
| T1 | **Input manipulation / adversarial inputs** | Crafted transaction amounts or vitals that push the fraud / clinical score just under a threshold; NaN/Inf or 10⁹-length sequences | Missed fraud, wrong clinical alert, model crash | Input guardrails, output caps, OOD detection |
| T2 | **Out-of-distribution (OOD) inputs** | New merchant category, new GPU SKU, sensor unit change | Confident but wrong predictions driving automation | OOD detector → flag & refuse to automate |
| T3 | **Data poisoning** | Mislabelled fraud data or skewed telemetry injected into training sets | Systematically biased model | Dataset provenance, evaluation gates, drift monitoring, integrity manifests on promoted models |
| T4 | **Model tampering / supply chain** | Swapped `.pt` file with a pickle payload or backdoored weights | Arbitrary code execution, silent misbehaviour | Model integrity manifests (SHA-256) verified **before** `torch.load` |
| T5 | **Runaway automation** | Remediation loop restarts a service 200×/hour; agent fails over every gateway at once | Self-inflicted outage | Allowlist, blast-radius limit, per-action and global rate caps, approval tiers, kill switch |
| T6 | **PHI / PII leakage** | Patient IDs in logs, model explanations or alert payloads | HIPAA / GDPR breach | Redaction of logs, audit entries and explanations; no PHI in alerts |
| T7 | **Abuse / DoS** | Credential stuffing on the API, scraping the fraud model, oversized bodies | Outage, model extraction, cost | API-key auth, per-client rate limiting, body size limits |
| T8 | **Repudiation** | "Who approved the VM cutover at 02:00?" | No accountability, failed audit | Hash-chained audit log with named approvers |

## Controls

### 1. Input guardrails & output caps — `golden/security/guardrails.py`

- Values must be finite (`ensure_finite`) and in physically plausible ranges (`ensure_in_range`,
  `check_bounds` with per-feature `FeatureBound`s).
- Sequences are capped at `MAX_SEQUENCE_LENGTH = 4096`, batches at `MAX_BATCH_SIZE = 10 000`.
- Scores leaving the platform are always clamped to `[0, 1]` (`clamp_score`).
- `OODDetector` fits a per-feature reference distribution and flags inputs beyond a z-score
  threshold (default 6σ). OOD inputs are still scored but **automation refuses to act** on them.
- Violations raise `GuardrailViolation(reason)` → HTTP 422 and
  `golden_guardrail_rejections_total{service,reason}`.

### 2. Action budgets & rate caps — `golden/security/actions.py`

The `ActionGovernor` evaluates every proposed action in this order:

1. **Kill switch** engaged → `blocked (kill_switch)`.
2. **Allowlist** — only actions in `ACTION_CATALOG` exist → otherwise `blocked (not_allowlisted)`.
3. **Blast radius** — at most `max_targets` (default 5) resources per action → `blocked (blast_radius)`.
4. **Global rate cap** — `GOLDEN_MAX_ACTIONS_PER_HOUR` (default 20) → `blocked (global_rate_cap)`.
5. **Per-action cap** — default 5 of the same action per hour → `blocked (action_rate_cap)`.
6. **Autonomy mode / approval tier** (below).

Blocks increment `golden_actions_blocked_total{reason}`.

### 3. Approval tiers

Every catalogued action carries a risk level:

| Risk | Examples |
|---|---|
| `low` | `scale_up_replicas`, `optimize_resources`, `throttle_api_clients`, `set_gpu_power_cap`, `reclaim_idle_gpus` |
| `high` | `restart_service`, `failover_payment_gateway`, `failover_ehr_gateway`, `consolidate_gpu_workloads`, `migrate_gpu_workload`, `drain_gpu_node` |
| `critical` | `isolate_fraud_transactions`, `halt_settlement`, `isolate_phi_breach`, `halt_clinical_pipeline`, `quarantine_patient_data`, `start_vm_migration`, `vm_cutover`, `vm_rollback` |

| `GOLDEN_AUTONOMY_MODE` | low | high | critical |
|---|---|---|---|
| `dry_run` (default) | simulate | simulate | simulate |
| `supervised` | execute | **human approval** | **human approval** |
| `autonomous` | execute | execute | **human approval** |

Critical actions **always** require a named human approver (`ActionGovernor.approve(request_id, approver)`),
whatever the mode. Pending requests are visible via `golden security status`.

### 4. Kill switch — `golden/security/killswitch.py` {#kill-switch}

- Engaged when `GOLDEN_KILL_SWITCH=true` **or** when the file named by `GOLDEN_KILL_SWITCH_FILE` exists
  (on Kubernetes: mount a ConfigMap key, or `kubectl exec … touch` the file in an emergency).
- Evaluated on every action — no restart needed. Detection and recommendations continue; nothing executes.
- Exported as `golden_kill_switch_engaged` (0/1); alert `KillSwitchEngaged` pages immediately.

### 5. Model integrity manifests — `golden/security/integrity.py`

- `write_manifest(dir)` records the SHA-256 of every model artifact into `manifest.json`.
- `safe_torch_load(path)` verifies the artifact against `GOLDEN_MODEL_MANIFEST`
  (or `<model_dir>/manifest.json`) **before** torch deserialises it; a mismatch raises `IntegrityError`.
- Generate the manifest in CI when a model is promoted, sign/commit it alongside the release,
  and set `required=True` in production.

### 6. Authentication & rate limiting — `auth.py`, `ratelimit.py`

- `GOLDEN_API_KEYS` (comma-separated) enables API-key auth; clients send `X-API-Key`.
  Keys are compared in constant time and only a fingerprint is ever logged.
  `/health`, `/ready` and `/metrics` stay unauthenticated for probes and scraping.
- Token-bucket limiting per client key/IP: `GOLDEN_RATE_LIMIT_PER_MINUTE` (default 600).
  Rejections return HTTP 429 and increment `golden_rate_limited_total{service}`.
- Request bodies are capped by `GOLDEN_MAX_BODY_BYTES` (default 1 MiB).

### 7. Hash-chained audit log — `golden/security/audit.py`

Each entry stores `seq`, timestamp, actor, event, data and `prev_hash`; its own hash covers all of
them. Editing or deleting any entry breaks the chain (`AuditLog.verify()`). File-backed when
`GOLDEN_AUDIT_LOG` is set; ship it to WORM storage (S3 Object Lock / Splunk audit index) for retention.

### 8. PHI / PII redaction — `golden/security/redaction.py`

`redact_text` / `redact_obj` remove `patient_id`, SSN, DOB, MRN, NPI, insurance IDs, card and account
numbers, e-mail addresses and secrets from logs, audit entries and model explanations. Alert
annotations never include record-level data.

## Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `GOLDEN_AUTONOMY_MODE` | `dry_run` | `dry_run` \| `supervised` \| `autonomous` (invalid values fall back to `dry_run`) |
| `GOLDEN_KILL_SWITCH` | `false` | Halt every autonomous action |
| `GOLDEN_KILL_SWITCH_FILE` | — | Kill switch engaged while this file exists |
| `GOLDEN_API_KEYS` | — (auth off) | Comma-separated API keys; enables `X-API-Key` auth |
| `GOLDEN_MAX_ACTIONS_PER_HOUR` | `20` | Global action budget |
| `GOLDEN_RATE_LIMIT_PER_MINUTE` | `600` | Per-client request rate limit |
| `GOLDEN_MAX_BODY_BYTES` | `1048576` | Maximum request body size |
| `GOLDEN_MODEL_MANIFEST` | `<model_dir>/manifest.json` | SHA-256 manifest verified before model load |
| `GOLDEN_AUDIT_LOG` | — (in-memory) | Path of the hash-chained audit log |

## Operating it

```bash
golden security status                         # mode, kill switch, budgets, pending approvals
GOLDEN_AUTONOMY_MODE=supervised golden orchestrate --cycles 3
GOLDEN_KILL_SWITCH=true golden orchestrate --cycles 1   # everything is blocked (kill_switch)
```

Observability: dashboard **Golden Platform — AI Safety** (`observability/grafana/dashboards/golden-ai-safety.json`)
and alert group `golden_ai_safety` (`observability/prometheus/rules/ai_safety_rules.yml`):
`KillSwitchEngaged`, `GuardrailRejectionSpike`, `GuardrailRejectionsSustained`, `ActionsBlockedSpike`,
`ActionBudgetExhausted`, `RateLimitingActive`, `AuthFailuresHigh`.

## Production checklist

- [ ] `GOLDEN_API_KEYS` set from a secret store (never in Git); keys rotated quarterly
- [ ] `GOLDEN_AUTONOMY_MODE=supervised` until the runbook has been exercised in a game day
- [ ] `GOLDEN_KILL_SWITCH_FILE` mounted from a ConfigMap the on-call can flip
- [ ] Model manifests generated in CI and verified with `required=True`
- [ ] `GOLDEN_AUDIT_LOG` shipped to immutable storage; `AuditLog.verify()` in the daily job
- [ ] AI-safety alerts routed to `#golden-ai-safety` and on-call
