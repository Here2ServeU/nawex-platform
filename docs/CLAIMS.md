# Claims Register

**Rule:** every number in these docs either has a command that reproduces it, or is labelled as a
**target**, an **illustration**, or **[needs source]**. Nothing here is a production or customer
result. There is no production deployment, no customer data and no measured uptime. The ML models are
trained and evaluated on synthetic data from [`src/golden/ai/datasets`](../src/golden/ai/datasets/README.md).

Status values:

- **Backed:** reproducible with the command or file shown. Measured values are quoted verbatim and are on synthetic or sample data.
- **Target:** an objective or design goal, labelled as such where it appears.
- **Reworded:** the original wording claimed more than the repo supports. The new wording is shown.
- **Removed:** no honest version exists, so the claim was deleted.
- **Cited (verify):** a third-party benchmark with a named source. It is kept, but the owner should check it against the current edition before quoting it.

All commands assume `GOLDEN_AGENTOPS_DIR` points at a scratch directory and run offline.

## Availability & resilience

| Claim (short) | Where (file) | Status | Evidence or new wording |
|---|---|---|---|
| API availability SLO 99.9% | [`observability/prometheus/rules/slo_rules.yml`](../observability/prometheus/rules/slo_rules.yml) (lines 27–35) | Target | Encoded as `SLOAvailabilityBreach` (`ratio_rate5m < 0.999`). This is an objective. Attainment has not been measured. |
| API latency SLO p95 < 500 ms | `slo_rules.yml` (lines 38–47) | Target | `SLOLatencyBreach` alert (`p95 > 0.5`). |
| "Achieves 99.999% availability" | guides/EXECUTIVE-PORTFOLIO.md, architecture/01, book-guide.md | Reworded | "The API availability SLO objective is 99.9%. No production uptime has been measured." |
| 99.999% availability objectives / KPI progression | executive/100M_PLATFORM_BLUEPRINT.md | Reworded | Start from the 99.9% objective. 99.99%+ is a later target, once the architecture is built and measured. |
| 99.999% uptime (SOX), 99.999% required by authorities (PSD2) | compliance/07, compliance/08 | Reworded | 99.9% SLO objective. Active-active (needed for higher tiers) is a design target. |
| Sub-30-second RTO | EXECUTIVE-PORTFOLIO, book-guide, compliance/04, compliance/07 | Reworded | "< 30 s RTO **target**, unmeasured. It needs a GSLB layer, which does not exist." |
| Zero RTO, near-zero RPO | architecture/05, compliance/02, compliance/04, compliance/07 | Reworded | Design targets. There is no cross-cloud replication code. |
| Multi-cloud active-active with GSLB | architecture/03, architecture/05, compliance/04, EXECUTIVE-PORTFOLIO | Reworded | Implemented: independent per-cloud landing zones in [`deploy/terraform/live`](../deploy/terraform) (`aws`, `azure`, `gcp`, `oci`) plus OpenShift assets. `git grep` over `deploy/` finds no GSLB, Route 53 failover, Front Door or Traffic Manager. Active-active is labelled "design target, not implemented". |
| "Zero-downtime for clinical operations" | architecture/03 | Reworded | "The goal is to minimise downtime." |
| Sub-second EKS→GKE handover, "zero interruption" | architecture/04 | Reworded | Target behaviour. Not implemented or measured. |
| Payment gateway failover within 5 s | architecture/04 | Reworded | Simulated in `payment-gateway` and exercised by [`payment-gateway-failure.sh`](../ops/sre/chaos/payment-gateway-failure.sh). Failover time not measured. |
| Kafka exactly-once for in-flight transactions | architecture/04, compliance/04, verticals/fintech.md | Reworded | Design only. `transaction_engine.py` keeps state in memory and does not use Kafka. |
| Fraud-model hot-swap / automatic shadow promotion | architecture/04, verticals/fintech.md, verticals/healthcare.md | Reworded | A gated registry with champion/challenger and rollback (`golden model`). A challenger is registered only if it passes the quality gate. |
| "Self-healing" (unqualified) | architecture/01, ai-engine/README.md, architecture/platform-overview.md, book-guide | Reworded | Governed self-healing: every action goes through the `ActionGovernor`, and the default autonomy mode is `dry_run` (`golden security status` → `"autonomy_mode": "dry_run"`). |
| "Systems that literally cannot fail" | compliance/04 | Removed | Replaced with "recovery is planned, has explicit targets and can be tested". |
| GitOps MTTR "approx. 60 seconds" | book-guide (GitOps section) | Reworded | Bounded by the reconciliation interval. Not measured. |
| DR runbooks RPO 15 min / RTO 1–2 h | book-guide (ops/dr copies) | Reworded | Marked "target, not yet tested". |
| Quarterly chaos / DR drills | compliance/04, compliance/07, compliance/06 | Reworded | Recommended cadence. No drill results exist yet. Scripts: [`ops/sre/chaos`](../ops/sre/chaos/README.md). |
| Transaction SLO 99.999% within 100 ms; sub-100 ms across regions | architecture/04, architecture/01 | Reworded | Target 99.9% within 100 ms. End-to-end latency not measured. |
| Health probes every 5 s via global LBs | compliance/04 | Reworded | Design. |
| 99.999% = "31 seconds downtime/year" | architecture/advanced-observability.md | Reworded | Arithmetic corrected: 99.999% is about 5.3 min/year (26 s/month). |
| 99.999% testing pyramid; DR flow "100% traffic in 30 s" | guides/enterprise-testing.md, guides/platform-integration.md | Reworded | Labelled as illustrative scenarios. |
| Custom SLA 99.99% add-on (+$5,000/month) | architecture/multi-tenancy.md | Target | Pricing proposal. Left as is; not an offered SLA. |

## AI / ML accuracy and latency

| Claim (short) | Where (file) | Status | Evidence or new wording |
|---|---|---|---|
| Fraud model metrics | EXECUTIVE-PORTFOLIO, architecture/04, consulting playbook, research/fraud | Backed | `golden model retrain --force --registry /tmp/reg` (deterministic seed, synthetic data) → precision **0.7532**, recall **0.9508**, F1 0.8406, AUC **0.9942**, FPR **0.0183**. |
| "92%+ prediction precision" | EXECUTIVE-PORTFOLIO, book-guide | Reworded | Replaced with the measured synthetic-data metrics above. |
| Precision/recall >92% clinical, >95% fraud; FPR <2% / <0.1% | architecture/04 | Target | Labelled as targets. The text notes they are not met on synthetic data today (precision 0.753, FPR 1.8%). |
| Fraud 95.6% precision / 92.3% recall | research/fraud_detection_methodology.md, research/lstm_sli_methodology.md, consulting playbook | Reworded | "Targets… not reproduced by any command — [needs source]". They are also hard-coded ROI defaults in [`impact_estimator.py`](../src/golden/ai/business_value/impact_estimator.py) (lines 131, 239–240). |
| Fraud FPR 0.08%, "18x / 18.75x fewer reviews" | consulting playbook, research/fraud | Removed (playbook) / Reworded (research banner) | The measured FPR is 1.83%. |
| Clinical 97.1% sensitivity / 94.5% specificity; 42% alarm-fatigue cut | research/clinical_safety_methodology.md | Reworded | Targets, [needs source]. Same values are ROI defaults (`impact_estimator.py` lines 63–64). |
| PHI 96.1% precision / 93.8% recall | research/phi_anomaly_methodology.md | Reworded | Targets, [needs source]. |
| LSTM R² 0.961, 53% RMSE cut; TCN 94.8% / 91.7% | research/lstm_sli_methodology.md | Reworded | Not reproduced. Re-measure with `make train` and record the output. |
| LSTM cuts MTTD by 73% | research/lstm_sli_methodology.md | Removed | "Aiming to reduce MTTD (the earlier 73% estimate is unsourced)". |
| "Production Deployed" status | all four research methodology docs | Reworded | "Reference implementation (synthetic data; not production-deployed)". |
| Fraud scoring latency (12.5 ms avg, sub-50 ms) | EXECUTIVE-PORTFOLIO, verticals/fintech.md, consulting playbook, research/fraud | Backed (in-process) + Target | In-process FastAPI `TestClient`, laptop, no network, 1,000 requests after 200 warm-up: **p50 0.73 ms, p95 1.95 ms, p99 2.70 ms** (command below). The 50 ms end-to-end budget is a target. 12.5 ms removed. |
| Fraud detector uses LSTM/TCN | verticals/fintech.md | Reworded | It is an explainable 5-signal composite ([`detect_fraud.py`](../src/golden/ai/pipelines/detect_fraud.py)). LSTM/TCN are SLI forecasters. |
| Sub-30 ms vital-sign scoring | verticals/healthcare.md | Reworded | 30 ms target, not measured. |
| Deterioration detected "4+ hours" / "30 minutes" early | consulting playbook | Reworded | Lead time not measured, [needs source]. The forecaster predicts 6 intervals ahead. |
| gRPC "sub-millisecond precision" | robotics/grpc.md, book-guide | Reworded | Low latency is a goal; not benchmarked. Broken `gemini.google.com` links removed. |
| gRPC "3–5x faster than JSON" | architecture/api-specifications.md | Reworded | "Smaller payloads and faster parsing; not benchmarked here". |
| GCP Vertex AI / TPU retraining loops | architecture/04, book-guide | Reworded | Design option. Training today: `make train` (CUDA → MPS → CPU) and `golden model retrain`. |

## Cost & ROI

| Claim (short) | Where (file) | Status | Evidence or new wording |
|---|---|---|---|
| Hospital: "$480,000/month risk protection" | consulting playbook | Reworded | `golden roi --vertical healthcare --json` → `monthly_value_protected_usd: 250476.1` (modelled from default assumptions, illustrative). |
| Bank: "$620,000/month protected value" | consulting playbook | Reworded | `golden roi --vertical fintech --json` → `monthly_value_protected_usd: 603076.45` (modelled). |
| ROI ratios / payback | output of `golden roi` | Backed (modelled) | Healthcare 14.3x, payback 2.1 days. Fintech 34.5x, payback 0.9 days. Both depend on the default assumptions (see the owner note below). |
| "3.6 cents per dollar of risk" | consulting playbook | Reworded | About 7 cents ($17,500 / $250,476). |
| "~$57M annual false-positive review savings" | consulting playbook | Removed | Based on the unreproducible 0.08% FPR. |
| "$252,000 saved at 45 min prevented downtime" | consulting playbook | Reworded | Labelled as an illustrative assumption. |
| SIEM "10,000 alerts → 50", "10x coverage", "integrate in days" | consulting playbook | Reworded | No ratio claimed. Integration is REST with OpenAPI; Kafka is a scoped project. |
| "12.5 ms — we'll put that in the contract SLA" | consulting playbook | Removed | Measure end-to-end p95 in the client environment during the pilot, then write the SLA from that. |
| Contract metrics: precision ≥ 90%, FPR ≤ 0.5%, uptime ≥ 99.9% | consulting playbook | Target | Baselined during Month 2 calibration. Current synthetic values are shown next to each one. |
| CMS $2,100/patient, OCR $1.9M/yr, $3,400 investigation, $22/review, "<0.1% of audit events reviewed" | consulting playbook | Reworded | Marked **[needs source]**. |
| $15,400/readmission (HIMSS 2024), $499/PHI record (IBM 2024), $45,700/h EHR downtime (Ponemon/Guidehouse), $1,200/fraud txn (Fed Reserve 2024), $2.4M AML fine (Deloitte 2024), $5,600/min downtime (Gartner) | consulting playbook, `impact_estimator.py` | Cited (verify) | Kept with their citations. The owner must confirm each figure and edition (see below). |
| SOX audit-prep effort cut by 80% | compliance/07 | Reworded | "Aimed at reducing… (no measured reduction)". |
| GPU utilization "routinely 20–40%"; power capping "10–25% energy for <5% throughput" | verticals/gpu.md | Reworded | Marked [needs source]. |
| "20–35% fewer GPUs, 10–20% lower energy per job" | verticals/gpu.md | Reworded | Replaced with sample output: `golden gpu analyze --scenario hot` → 64 GPUs, 43.5% avg utilization, 12 idle, 3 nodes freeable (synthetic fleet). |
| Agent run $0.04 guarded / $0.14 cap-only / ~$975 unguarded overnight | agent-operations/README.md | Backed | `golden agent verify` → guarded `0.041782`, cap-only `0.140344`. `golden agent overnight` → `unguarded_overnight_usd: 974.49` (assumptions: 3 s/step, 12 workers, 9.5 h). |
| Sample migration readiness | consulting playbook (fixed-scope offers) | Backed | `golden migrate assess` → 16 VMs: 8 ready, 6 need remediation, 2 blocked (sample inventory). |
| Sample IAM role reduction | consulting playbook (fixed-scope offers) | Backed | `golden iam roles` → 40 roles, `role_reduction_pct: 58.3` (sample estate). |
| README quick start "~5 minutes" | README.md | Reworded | "(local)". The time was never measured; `make bootstrap` installs the ML extras. |

## Compliance

| Claim (short) | Where (file) | Status | Evidence or new wording |
|---|---|---|---|
| HIPAA / SOC 2 / PCI / SOX "compliant", "maintains adherence" | EXECUTIVE-PORTFOLIO, architecture/01, book-guide | Reworded | "Control mappings, not certifications". Every compliance doc now opens with a **Mapping, not certification** banner. |
| "Compliant product" | compliance/01 | Reworded | A covered entity can take the product through its own risk analysis. The product is not HIPAA-compliant on its own. |
| "Platform satisfies the six HDS activities" | compliance/02 | Reworded | Certification applies to the hosting provider, not to this template. |
| PCI DSS Level 1 Service Provider certification path | compliance/06 | Reworded | Needs the design items implemented plus a QSA ROC/AOC. |
| PAN tokenization at Kong, token vault | compliance/06, EXECUTIVE-PORTFOLIO | Reworded | Design. No tokenization code exists. |
| Falco runtime scanning, Sigstore/Cosign provenance | compliance/06 | Reworded | Recommended, not configured. Trivy in CI is real. |
| WORM / object-locked log buckets | compliance/03, compliance/06, compliance/07 | Reworded | Deployment requirement. `deploy/terraform` does not provision log object-lock buckets. |
| Tamper-evident audit chain | compliance/03, EXECUTIVE-PORTFOLIO | Backed | [`src/golden/security/audit.py`](../src/golden/security/audit.py) (SHA-256 of predecessor). `golden security status` → `"audit_chain_valid": true`. |
| Terraform state encrypted and locked | architecture/03 | Backed | [`deploy/terraform/modules/aws/backend/main.tf`](../deploy/terraform/modules/aws/backend/main.tf) (KMS key, versioning, SSE, public-access block, lock table). |
| Cloud providers "are SOC 2 Type II certified" | compliance/06, compliance/09 | Reworded | Inherited control. Providers publish attestations; verify current reports. |
| Real-time evidence to Big Four auditors | compliance/07 | Reworded | "Intended to help the organisation provide evidence". |
| PSD2 SCA / FAPI 2.0 compliance / eIDAS | compliance/08 | Reworded | Design items for the Kong gateway. Only transaction risk scoring is implemented. |
| Auto-block at P > 0.90 and customer notified in 30 s | compliance/08 | Reworded | `fraud-detector` flags `is_fraud` at `FRAUD_THRESHOLD` (default 0.75). Blocking and notification belong to the integration. |
| PSD2 Art. 96 incidents flagged within 4 h automatically | compliance/08, compliance/04, architecture/04 | Reworded | Process requirement. Not automated here. |
| GLBA privacy-notice APIs, opt-out, DLP | compliance/09 | Reworded | Design. Redaction of PHI/PII in logs is real ([`redaction.py`](../src/golden/security/redaction.py)). |
| "PCI-DSS compliant data handling", "FHIR/HL7-compliant" | verticals/fintech.md, verticals/healthcare.md | Reworded | Design target; "FHIR/HL7-style (simulated)". |
| Keycloak "HIPAA-compliant option" | guides/platform-integration.md | Reworded | "Can be deployed in a HIPAA-aligned configuration". |

## Quantum

| Claim (short) | Where (file) | Status | Evidence or new wording |
|---|---|---|---|
| Hybrid quantum-classical QNN/LSTM/TCN ensemble | EXECUTIVE-PORTFOLIO, book-guide copy | Removed | `git grep -niE "qiskit\|pennylane\|qaoa\|qnn" -- ':!*.md'` returns nothing. |
| QAOA sub-millisecond multi-cloud routing | EXECUTIVE-PORTFOLIO | Removed | No code. |
| Quantum kernels at the robotics edge; quantum MLOps / simulators | EXECUTIVE-PORTFOLIO | Removed | No code. |
| "Quantum-safe network nodes / clusters" | EXECUTIVE-PORTFOLIO | Removed | No code. |
| "Quantum-Enhanced" platform title | EXECUTIVE-PORTFOLIO | Removed | Retitled "Predictive Safety & Resilience Platform". |
| Quantum Optimization Layer as a capability | architecture/06-quantum-optimization-layer.md, docs/README.md | Reworded | "Research note — not implemented in this repository". The body is now framed as future work. |
| PQC implemented (Kyber, Dilithium, PQC-signed logs, transaction signing, HSM offload) | compliance/05, compliance/09, EXECUTIVE-PORTFOLIO | Reworded | A **PQC readiness plan**: crypto inventory, then prioritisation, then hybrid migration to FIPS 203/204/205. |

## Scale, market & product surface

| Claim (short) | Where (file) | Status | Evidence or new wording |
|---|---|---|---|
| "$100M-class enterprise platform" | executive/100M_PLATFORM_BLUEPRINT.md | Reworded | A long-term ambition, not revenue, valuation or customer count. There are no production customers. |
| Blueprint code paths (`platform/telemetry`, `healthcare/…`, `sre/…`, `deploy/networking`) | executive/100M_PLATFORM_BLUEPRINT.md | Reworded | Repointed to the v2 paths that exist (`src/golden/...`, `ops/sre/...`, `deploy/openshift`). |
| "Production-hardened implementation" | EXECUTIVE-PORTFOLIO, book-guide | Reworded | "Reference implementation… synthetic data; not deployed in production". |
| GraphQL API | architecture/api-specifications.md, guides/developer-onboarding.md, guides/platform-integration.md | Removed | No GraphQL code (the only GraphQL in `src` is the Wiz export parser input). |
| SDKs (`pip install golden-sdk`, npm, Go, Java, C#) | architecture/api-specifications.md | Reworded | "Planned SDKs (not published)". |
| API v2 stability commitment | architecture/api-specifications.md | Reworded | "Proposed API stability policy (no external consumers yet)". |
| Customer counts, ARR, valuation, market size | all docs | n/a | None found. |

## How to replace targets with measurements

Run these on a real deployment and replace the matching target in the docs with the measured
value, the date, and the environment.

| What | How to capture it | Replaces |
|---|---|---|
| **Deploy time** | Wall-clock time of `time make deploy CLOUD=<aws\|azure\|gcp\|openshift> ENV=<env>` from an empty account. Record the cloud, region and node sizes. | Platform jumpstart "~30 days" scoping; any "one-command deploy" timing |
| **Monthly cost** | `infracost breakdown --path deploy/terraform/live/<cloud>/<env>` before apply, then the actual cloud bill after 30 days. | Pricing and ROI cost lines; GPU savings |
| **p95 latency under load** | Run `k6 run tools/k6/transaction-load.js` (transactions, :8090) and `tools/k6/load-test.js`; add a fraud-scoring scenario for `/v1/fraud/score`. Read `service:golden_http_request_duration_seconds:p95` from Prometheus. | Fraud 50 ms budget, transaction 100 ms target, vitals 30 ms target, `p95 < 500 ms` SLO attainment |
| **Availability** | 30-day attainment of `service:golden_http_requests_success:ratio_rate5m` against 0.999. | 99.9% objective → measured attainment |
| **Recovery time** | Run a chaos script from [`ops/sre/chaos`](../ops/sre/chaos/README.md) (`pod-kill-test.sh`, `node-failure-test.sh`, `region-failover-test.sh`, `payment-gateway-failure.sh`). Time from fault injection until the SLO recording rule is back above objective. | RTO targets (< 30 s, 1–2 h runbook), payment failover "5 s" |
| **Model metrics** | `make train` (LSTM/TCN) and `golden model retrain --force` (fraud). On client data, rerun after Month 2 calibration. | Research methodology figures, contract precision/FPR targets |
| **ROI** | `golden roi --vertical <v> --json` with the client's volumes and measured model metrics in place of the defaults in `impact_estimator.py`. | Consulting playbook value figures |

### Reproducing the in-process fraud-scoring latency

```bash
.venv/bin/python - <<'PY'
import time, random
from fastapi.testclient import TestClient
from golden.services.fintech.fraud_detector import app
c = TestClient(app); ts = []
for i in range(1200):
    body = {"transaction_id": str(i), "account_id": f"a{i%50}", "amount": random.uniform(1, 5000),
            "channel": "online", "country_code": "US", "merchant_category_code": "5411"}
    t = time.perf_counter(); c.post("/score", json=body); ts.append((time.perf_counter() - t) * 1000)
ts = sorted(ts[200:])
print("p50 %.2f p95 %.2f p99 %.2f ms" % (ts[500], ts[950], ts[990]))
PY
```

This measures in-process scoring only: no network, no gateway and no concurrency. Do not quote it
as end-to-end latency.

## Open items for the owner

- **ROI defaults:** `impact_estimator.py` hard-codes model precision 0.956 / recall 0.923 and sensitivity 0.971 / specificity 0.945. The trained fraud model measures 0.753 / 0.951. Either feed measured metrics into `golden roi` or label its output as assumption-driven. The CLI summary text ("generates 14x ROI…") reads like a result.
- **Cited benchmarks:** confirm each "Cited (verify)" figure against its source. For example, IBM's Cost of a Data Breach report gives per-record costs that vary by edition and industry, and the Gartner $5,600/min figure dates from 2014.
- **Pricing tiers** ($10K / $17.5K / $25K per month) are a business decision. They are kept as is.
