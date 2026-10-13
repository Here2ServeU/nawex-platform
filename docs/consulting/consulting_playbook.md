# Golden Platform Consulting Playbook

**Rev. Dr. Emmanuel Naweji, PhD — Golden Platform**
**Version 2.0 | April 2026 | Confidential**

---

## Overview

This playbook guides Golden Platform consulting engagements from first contact through
signed contract. Target clients are hospital systems and financial institutions
with the budget and regulatory mandate for enterprise AI risk management at
$10,000–$25,000/month.

> **Rules for numbers in this playbook.** Every dollar or percentage figure is one of:
> (a) **modelled** — produced by `golden roi --vertical <v> --json` from stated default assumptions in
> [`impact_estimator.py`](../../src/golden/ai/business_value/impact_estimator.py), to be re-run with the client's own volumes;
> (b) **measured on synthetic data** — reproducible with the command given;
> (c) **third-party benchmark** — cited; verify against the current edition before quoting; or
> (d) marked **[needs source]** — do not say it in a meeting until a source is found.
> There are no production customers yet; nothing here is a customer result. See [CLAIMS.md](../CLAIMS.md).

---

## Pricing Tiers

| Tier | Monthly | Annual | Ideal Client |
|------|---------|--------|-------------|
| **Starter** | $10,000 | $120,000 | Community hospital (≤250 beds) / Community bank |
| **Professional** | $17,500 | $210,000 | Regional health system / Mid-size bank |
| **Enterprise** | $25,000 | $300,000 | Health network / National bank |

All tiers include:
- Real-time AI dashboard (Golden Platform Client Portal)
- Full explainability reports
- Regulatory alignment documentation
- Quarterly model performance reviews
- Dedicated research support

---

## Fixed-scope offers

Short, fixed-price engagements that end in a deliverable the client keeps. Each deliverable is produced by a command in this repository, so the work is repeatable and the output can be shown in the first meeting using the bundled sample data.

| Offer | Duration | Client inputs | Deliverables | Produced by |
|---|---|---|---|---|
| **VMware exit assessment** | 2–3 weeks | RVTools export (vInfo/vDisk/vNetwork CSVs or the export directory); app owners and change windows | Readiness report (ready / needs remediation / blocked, with blocker reasons), dependency-aware migration waves, MTV manifests per wave for GitOps, cutover and rollback runbooks | `golden migrate assess --inventory <rvtools-dir>`, `golden migrate plan --inventory <rvtools-dir>`, `golden migrate manifests --inventory <rvtools-dir> --output <dir>`; runbooks in [`ops/runbooks/migration`](../../ops/runbooks/migration/cutover.md) |
| **AWS IAM modernization assessment** | 2–3 weeks | `aws iam get-account-authorization-details` JSON per account; Wiz issues export (CSV or GraphQL JSON); AD group list | Role cleanup / consolidation / Identity Center migration plan (keep, remove, consolidate, migrate to permission set), control-gap register mapped to the control-placement catalog | `golden iam roles --input <auth-details.json>`, `golden iam gaps --wiz <wiz-export.csv>`, `golden iam controls`, `golden iam model` — see [aws-iam-modernization.md](../modernization/aws-iam-modernization.md) |
| **Platform jumpstart** | ~30 days | Target cloud account/subscription/project, region, OIDC trust for CI, naming conventions | Landing zone (Terraform) plus the platform (Helm/GitOps), observability stack, SLOs and alert rules, runbooks, handover session | `make plan CLOUD=<aws\|azure\|gcp\|openshift> ENV=<env>` then `make deploy CLOUD=<cloud> ENV=<env>` — see [deploy guide](../guides/deploy.md) |
| **AI governance / agent operations review** | 2 weeks | Inventory of AI agents and LLM use cases, current guardrails, model/provider spend | Review of action governance (`ActionGovernor` autonomy modes, approvals, kill switch, audit chain), guardrail and red-team results, agent cost controls (budgets, loop detection, checkpoints, cost per successful task) and an unguarded-spend estimate | `golden security status`, `golden agent verify`, `golden agent overnight`, `golden agent redteam`, `golden agent report` — see [agent-operations](../agent-operations/README.md) and [AI safety](../security/ai-safety.md) |

Sample outputs on the bundled sample data (not client data): `golden migrate assess` → 16 VMs, 8 ready, 6 need remediation, 2 blocked; `golden iam roles` → 40 roles, 58.3% role reduction proposed; `golden agent overnight` → $974 projected unguarded overnight spend vs $0.04 guarded run (assumptions printed in the output).

---

## Hospital Consulting Pitch

### Target Buyer
- **Primary:** Chief Information Officer (CIO) / Chief Medical Information Officer (CMIO)
- **Secondary:** Chief Compliance Officer / Privacy Officer
- **Influencer:** Chief Medical Officer (CMO)

### Opening Hook (30 seconds)
> *"Your EHR generates millions of audit events every month —
> and most are never reviewed by a person [needs source for a review-rate figure]. Golden Platform uses
> explainable AI to surface the small share that carry real risk,
> so your team focuses on what matters. Our ROI model, run with default
> assumptions for a mid-size hospital (450 monitored patients/day), estimates about
> $250,000 per month in readmission, breach and downtime risk exposure addressed —
> on a $17,500/month contract. We'll re-run it with your numbers."*
>
> Source of the $250K figure: `golden roi --vertical healthcare --json` → `monthly_value_protected_usd: 250476` (modelled, illustrative; assumes model sensitivity 0.971 / specificity 0.945, which are design defaults, not measured results).

### Key Value Propositions

**1. Readmission Prevention (CMS HRRP)**
- Golden Platform's clinical AI scores patient vitals in real time against NEWS2-style
  thresholds, aiming to flag deterioration earlier than single-threshold alerts
  (lead time not measured [needs source])
- Aligned with NEWS2 (Royal College of Physicians) and Sepsis-3 criteria
- **Dollar impact:** $15,400 per avoided readmission (HIMSS 2024)
- **Talking point:** "CMS penalties for excess readmissions are material [needs source for a per-patient figure].
  We aim to flag the deterioration that leads to a readmission earlier."

**2. HIPAA PHI Breach Prevention**
- AI-powered access anomaly detection catches insider threats and
  accidental PHI exposure — aligned with §164.312(b)
- **Dollar impact:** $499 per PHI record breached (IBM Cost of Breach 2024)
- Illustrative arithmetic: a 500-record breach × $499 = ~$250,000 exposure
- **Talking point:** "OCR civil penalties have an annual cap per violation category in the millions
  [needs source: cite the current inflation-adjusted cap, 45 CFR 160.404]. Golden Platform aims to reduce your exposure by flagging anomalous
  access before it becomes a breach."

**3. EHR Reliability (Downtime Prevention)**
- LSTM/TCN AI predicts EHR latency SLO breaches 6 intervals ahead,
  enabling proactive scaling before downtime occurs
- **Dollar impact:** $45,700/hour EHR downtime cost (Ponemon/Guidehouse)
- **Talking point:** "We aim to prevent the 2am call to IT. The forecaster predicts 6 intervals ahead,
  so lead time depends on your scrape interval; remediation such as scaling runs through approval gates."

**4. Regulatory Standing**
- Audit trail augmentation mapped to HIPAA §164.312(b) (tamper-evident, hash-chained)
- NIST SP 800-66r2 implementation guidance alignment
- Supports Joint Commission NPSG.06.01.01 alarm-management work (not a compliance attestation)
- HHS OCR investigation-ready explainability reports

### Objection Handling

| Objection | Response |
|-----------|----------|
| "We already have SIEM/EHR alerts" | "Golden Platform augments those tools — it's not a replacement. It ranks your existing alerts by explainable risk so the team starts with the few that matter." (Use the client's own alert volume; no reduction ratio has been measured.) |
| "Our IT team handles this" | "Golden Platform gives your IT team more coverage with the same headcount." (No coverage multiple is claimed [needs source].) |
| "The budget isn't there" | "Our model estimates ~$250,000/month of risk exposure addressed on a $17,500/month contract — about 7 cents per modelled dollar. Let's re-run it with your data in the pilot." (modelled, `golden roi --vertical healthcare`) |
| "Data privacy concerns" | "Golden Platform processes your data in your environment. We never receive PHI — the AI runs on-premises or in your private cloud." |
| "We need to see the research" | "Here's the methodology documentation and the code. Models are trained and evaluated on synthetic data today; the pilot calibrates and measures them on yours." |

---

## Financial Institution Consulting Pitch

### Target Buyer
- **Primary:** Chief Risk Officer (CRO) / Head of Fraud Operations
- **Secondary:** BSA/AML Compliance Officer
- **Influencer:** CTO / Head of Payments

### Opening Hook (30 seconds)
> *"Your fraud team manually reviews thousands of flagged transactions
> every day at a real cost per review [needs source for the $22 figure]. Golden Platform
> scores every transaction with an explainable 5-signal model in about 2 ms in-process,
> so scoring adds almost nothing to your payment path. Our ROI model, with default
> assumptions for a 500,000-transaction/day bank, estimates about $600,000/month in
> fraud, downtime and compliance exposure addressed on a $17,500/month contract.
> We'll re-run it with your numbers."*
>
> Sources: latency — in-process p95 ≈ 2 ms on a laptop, no network (see [CLAIMS.md](../CLAIMS.md)); value — `golden roi --vertical fintech --json` → `monthly_value_protected_usd: 603076` (modelled; assumes precision 0.956 / recall 0.923 as design defaults — the trained model measures precision 0.753 / recall 0.951 on synthetic data via `golden model retrain --force`).

### Key Value Propositions

**1. Fraud Loss Prevention**
- 5-signal composite fraud scoring: amount anomaly, velocity, geo risk,
  channel risk, MCC risk — aligned with Federal Reserve Payments Study 2024
- **Dollar impact:** $1,200 avg fraudulent transaction (Fed Reserve 2024)
  + $3,400 investigation cost [needs source]
- **Talking point:** "Scoring happens inline, before settlement, in a few milliseconds,
  so suspicious payments can be held instead of investigated after the fact."

**2. AML/BSA Compliance Automation**
- Pattern detection aligned with FATF mutual evaluation criteria
- SAR filing-ready explainability reports (Part III, Section 35)
- **Dollar impact:** $2.4M average AML fine (Deloitte 2024)
- **Talking point:** "When your examiners ask how you detected the suspicious
  pattern, Golden Platform gives you the AI audit trail and the human-readable explanation."

**3. Payment Reliability**
- LSTM/TCN predicts gateway SLO breaches, enabling proactive failover
- **Dollar impact:** $5,600/minute payment downtime (Gartner)
- Illustrative: *if* 45 minutes of downtime/month were prevented, $5,600 × 45 = $252,000 (assumption, not a measured outcome)
- **Talking point:** "If your payment SLA is 99.99%, you have about 4 minutes of budget a month.
  Golden Platform forecasts SLO breaches ahead of time so failover can start earlier." (Lead time not measured.)

**4. False Positive Reduction**
- Industry average FPR ~1.5% (McKinsey 2023 — verify). Golden Platform's FPR on synthetic data
  is 1.8% for the trained model (`golden model retrain --force`); the earlier 0.08% figure
  was not reproducible and has been removed.
- **Dollar impact:** reviews avoided × cost per review — compute with the client's own FPR baseline
  and review cost during the pilot. No savings figure is claimed until then.
- **Talking point:** "Your fraud analysts are expensive. We let them work on
  real threats instead of noise."

### Objection Handling

| Objection | Response |
|-----------|----------|
| "We have in-house fraud models" | "Golden Platform complements your models. Our explainability layer works on top of any existing system." |
| "Regulatory risk of AI in compliance" | "Golden Platform produces fully auditable, explainable decisions — no black box. Your examiners can review every flag." |
| "Performance SLA concerns" | "In-process scoring is about 2 ms p95 on a laptop. We'll measure end-to-end p95 in your environment during the pilot and write the SLA from that measurement." |
| "Integration complexity" | "Golden Platform exposes REST APIs with OpenAPI docs today; Kafka integration is a scoped project. We'll size it in the assessment." |

---

## Demo Preparation Checklist

Before a client meeting, run:

```bash
# 1. Start the live dashboard (most impactful visual)
cd apps/client-portal && npm install && npm start

# 2. Pre-run the terminal demo for polish
golden demo client --vertical hospital --client "Demo"

# 3. Have the HTML report ready as a leave-behind template
```

**Meeting setup:**
- [ ] Client portal open on laptop: `http://localhost:3001`
- [ ] Switch to appropriate vertical (Hospital or Bank toggle)
- [ ] Research methodology docs printed or on tablet
- [ ] Pricing sheet ready (Starter/Professional/Enterprise)
- [ ] ROI calculations customized for client size

**Recommended meeting structure (45 min):**
1. (5 min) Platform overview — what Golden Platform is
2. (10 min) Live dashboard walkthrough — they see the AI working
3. (10 min) Terminal demo — impressive technical credibility
4. (10 min) ROI discussion — customized for their institution size
5. (5 min) Research methodology — answers the "how does it work?" question
6. (5 min) Pricing and next steps

---

## Contract Structure

**Standard Terms:**
- 3-year initial term (quarterly ROI reviews)
- Month 1: Onboarding and integration
- Month 2: Model calibration to client data
- Month 3+: Full production monitoring

**Success metrics to set in contract (targets, baselined during Month 2 calibration on client data — do not commit to them before):**
- Alert precision ≥ 90% (synthetic-data fraud model today: 75%)
- False positive rate ≤ 0.5% (synthetic-data fraud model today: 1.8%)
- Platform uptime ≥ 99.9% (matches the SLO objective in `observability/prometheus/rules/slo_rules.yml`)
- Report delivery within 4 hours of incident

**Negotiation guidance:**
- Never discount below $10,000/month (cheapens the research brand)
- Annual prepay: 10% discount acceptable
- Pilot: 90-day paid pilot at Starter tier ($10K/month) is a good on-ramp
