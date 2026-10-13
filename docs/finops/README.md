# FinOps — Cost Visibility, Allocation and Optimization

How the platform makes cloud and Kubernetes spend visible, assigns it to the teams that cause it, and
turns it into decisions. It follows the FinOps Foundation lifecycle (Inform → Optimize → Operate) and
uses FOCUS as the single data format, so the same analysis runs on AWS, Azure and Google Cloud bills.

Platform pieces used here:

| Piece | Location |
|---|---|
| AWS budgets, Cost Anomaly Detection, FOCUS Data Export, cost allocation tags | `deploy/terraform/modules/aws/finops` |
| Azure consumption budgets (subscription, team tag, resource group) + cost export | `deploy/terraform/modules/azure/finops` |
| GCP billing budgets + Pub/Sub notifications + BigQuery billing export dataset | `deploy/terraform/modules/gcp/finops` |
| Plan-time tagging gate (OPA) | `security/policies/opa/tagging.rego` (+ `tagging_test.rego`) |
| FOCUS loader, showback/chargeback, anomalies, forecasts, recommendations | `src/golden/finops/` (`golden.finops`) |
| Kubernetes cost allocation | OpenCost: `deploy/gitops/argocd/app-opencost.yaml`, `deploy/gitops/flux/apps/resources/opencost-helmrelease.yaml` |
| Kubernetes cost alerts | `observability/prometheus/rules/finops_rules.yml` |
| Cost estimate on every Terraform PR | `.github/workflows/infracost.yml` |
| Tests | `tests/test_finops.py` |

## 1. The lifecycle

| Phase | Question | What answers it here |
|---|---|---|
| **Inform** | Who spends what, on what, and is it attributed? | FOCUS exports from all three clouds · tag coverage · showback by team/cloud/service · OpenCost namespace costs · Infracost on PRs |
| **Optimize** | Where are we paying for nothing, or paying list price? | Idle and rightsizing recommendations · commitment (Savings Plan / RI / CUD) sizing · Kubernetes idle ratio |
| **Operate** | How do we keep it that way? | Budgets with actual + forecast alerts · anomaly detection · the OPA tagging gate · chargeback · unit economics reviewed with product owners |

The phases are a loop, not a sequence. Each month: refresh the data (Inform), act on the top items
(Optimize), and adjust budgets, tags and policy (Operate).

## 2. FOCUS: one cost schema for every cloud

FOCUS (FinOps Open Cost and Usage Specification) defines common billing columns. The ones
`golden.finops` relies on:

| Column | Meaning |
|---|---|
| `BilledCost` | What appears on the invoice for the row |
| `EffectiveCost` | Amortized cost after commitment discounts (upfront fees spread over the term). **Use this for allocation.** |
| `ListCost` | Cost at public on-demand prices; `ListCost - EffectiveCost` is the realized discount |
| `ChargePeriodStart` | Start of the charge period (hour or day) |
| `ServiceName` / `ServiceCategory` | Provider service and its FOCUS category (Compute, Storage, Networking, ...) |
| `ProviderName` / `SubAccountId` / `RegionId` / `ResourceId` | Where the cost came from |
| `Tags` | Resource tags/labels as JSON |

Sources:

- **AWS** — Data Exports (the CUR 2.0 family) with the `FOCUS_1_0_AWS` table, written as Parquet to an
  encrypted S3 bucket by `modules/aws/finops`. The Data Exports API is served from `us-east-1`.
- **Azure** — Cost Management exports. `modules/azure/finops` creates a daily `AmortizedCost` export
  (azurerm 3.x does not model the FOCUS export type); the FOCUS dataset can also be selected in the
  portal. `golden.finops` maps the native columns (`CostInBillingCurrency`, `MeterCategory`,
  `SubscriptionId`, ...) onto FOCUS.
- **GCP** — Cloud Billing detailed usage cost export to BigQuery. `modules/gcp/finops` creates the
  dataset; the export itself is switched on in the console (Billing → Billing export), because Cloud
  Billing has no API for it. Google publishes a FOCUS view over that export.

`golden.finops.load_focus()` accepts FOCUS CSV or the native AWS CUR, Azure and GCP column names and
returns one normalized frame. `sample_focus_data()` generates a deterministic month across the three
clouds, four teams and shared services, with about 5% untagged spend and one injected cost spike.

```python
from golden.finops import finops_report, load_focus, showback

report = finops_report()                    # sample data, everything in one dict
costs = load_focus("focus-2026-09.csv")      # or a real export
print(showback(costs, "Team").to_dict())
```

## 3. Tagging strategy and enforcement

Required tags (labels on GCP), the same list everywhere:

| Tag | Purpose | GCP label |
|---|---|---|
| `Project` | Product or programme | `project` |
| `Environment` | dev / staging / prod / sandbox / shared | `environment` |
| `Team` | Owning team: the allocation key for showback, budgets and anomaly monitors | `team` |
| `CostCenter` | Finance cost center for chargeback | `cost_center` |
| `Owner` | Contact (team alias, not a person where possible) | `owner` |

GCP label keys must be lowercase, so keys are compared case- and separator-insensitively everywhere
(`CostCenter` = `cost_center` = `cost-center`) — in the OPA policy and in `golden.finops.tag_value`.

Enforcement is layered. Each layer catches what the one before it missed:

| Layer | Mechanism | Catches |
|---|---|---|
| 1. Defaults | AWS provider `default_tags` (`live/aws/*`), GCP provider `default_labels`, module `tags` variables | Most resources get the tags without anyone typing them |
| 2. Plan gate | `security/policies/opa/tagging.rego` on `terraform show -json` | Taggable resources in a plan missing a required tag. It reads `tags_all` (AWS, includes `default_tags`), `tags` (Azure) and `effective_labels` (GCP, includes `default_labels`); values only known after apply count as present; blank values count as missing |
| 3. Cloud policy | AWS Organizations **tag policies** (allowed keys/values, case) · **Azure Policy** built-in "Require a tag on resources" / "Inherit a tag from the resource group" · GCP **org policy custom constraints** on resource labels | Resources created outside Terraform (console, CLI, other pipelines) |
| 4. Detection | `golden.finops.tag_coverage()` on the bill; cost allocation tags activated by `modules/aws/finops` | What still slips through, measured in dollars, with the costliest untagged resources listed |

Run the gate locally:

```bash
terraform -chdir=deploy/terraform/live/aws/dev plan -out tf.plan
terraform -chdir=deploy/terraform/live/aws/dev show -json tf.plan > plan.json
opa eval -d security/policies/opa -i plan.json 'data.golden.finops.tagging.deny'
```

Override the required set or exempt specific addresses with a data document
(`{"finops": {"required_tags": [...], "exempt_addresses": [...]}}`). Untaggable resource types (IAM
attachments, routes, security group rules) are not checked; the taggable list is in the policy.

## 4. Budgets and anomaly detection

Budgets catch slow drift against a plan; anomaly detection catches sudden spikes that are small next to
a monthly budget but large next to a normal day.

| | AWS | Azure | GCP |
|---|---|---|---|
| Account/subscription/project budget | `aws_budgets_budget` | `azurerm_consumption_budget_subscription` | `google_billing_budget` |
| Per-team budget | Cost filter `TagKeyValue = user:Team$<team>` | Subscription budget with a `Team` tag filter | Budget filter `labels = {team = <team>}` |
| Alerts | ACTUAL 50/80/100% + FORECASTED 100% → SNS + email | Actual + Forecasted → email + action groups | CURRENT_SPEND + FORECASTED_SPEND → Pub/Sub + Monitoring channels |
| Anomalies | Cost Anomaly Detection: SERVICE monitor + Team tag monitor; IMMEDIATE to SNS, DAILY to email; alert when impact ≥ $X **or** ≥ Y% | Cost Management anomaly alerts (portal) | Budget Pub/Sub stream + `golden.finops` |

`golden.finops` runs the same checks over any FOCUS data, by service or by tag:

- `detect_anomalies(frame, by="Team")` — per group, compares each day with the median of the previous
  14 days using a robust z-score (median and MAD instead of mean and standard deviation, so one spike
  does not hide itself). A day is flagged when the score is ≥ 3.5 **and** the excess is ≥ $25.
- `forecast_month_end(frame)` — straight-line fit through month-to-date daily cost, summed to month end.
- `budget_status(frame, {"payments": 24000, "total": 120000})` — `over` (actual > budget), `at_risk`
  (forecast > budget), `warning` (actual ≥ 80%) or `ok`, matching the cloud budget notifications.

## 5. Showback, chargeback and shared costs

- **Showback** reports what each team spent. Untagged cost stays visible as its own `untagged` line,
  because that line is the work queue for tagging.
- **Chargeback** bills it. Every dollar must land on a cost center, so untagged cost is spread across
  teams in proportion to their direct spend. Start with showback; move to chargeback once tag coverage
  is high enough that the spread is small.

Shared costs — NAT gateways, transit/hub networking, the observability stack, security tooling — are
used by everyone and owned by the platform team. Tag them `Team=shared` (or pass the services/categories
to `shared_services`) and choose how to split the pool:

| Method | Use when |
|---|---|
| `proportional` (default) | Usage of the shared service roughly follows overall spend |
| `even` | Each team gets roughly the same benefit (e.g. a security baseline) |
| `fixed` | You have a better driver (request counts, log volume) — pass `weights={"payments": 0.5, ...}` |

`allocate()` returns direct, shared and untagged parts per owner, and the parts always add up to the
total bill.

## 6. Unit economics

Total spend going up is fine if the business is growing faster. Unit cost tells you which:

```python
unit_economics(chargeback(costs), {"payments": 41_500_000, "total": 310_000_000}, unit="transactions")
# -> cost per transaction and per 1,000 transactions, per team and platform-wide
```

Use fully loaded (chargeback) totals, pick a unit the product owner already tracks (transactions,
requests, active users, GB processed), and review the trend monthly rather than the absolute number.

## 7. Optimization: rightsizing and commitments

`golden.finops.recommendations` turns utilization samples into tickets. Each recommendation has an
estimated monthly saving and a confidence (`high` ≥ 14 days of hourly samples, `medium` ≥ 7 days,
otherwise `low`).

| Recommendation | Rule |
|---|---|
| Terminate idle | p95 CPU < 5% (and p95 memory < 20% when sampled). Saving = the whole cost |
| Rightsize | Needed vCPUs = vCPUs × max(p95 CPU, p95 memory) × 1.25 headroom, rounded up to the next size; saving assumes price scales with size within a family |
| Commitment | Commit at the **p10** of hourly on-demand-eligible spend (the floor you pay ~90% of hours), minus what is already committed. Saving = commitment × discount × 730 h. Confidence drops when spend is volatile |

Order of operations matters: remove idle resources and rightsize **before** buying commitments, or you
commit to waste. Re-run the commitment sizing monthly and buy in small increments rather than one large
purchase.

## 8. Kubernetes cost allocation

Cloud bills stop at the node. OpenCost splits each node's price into CPU and RAM parts and charges every
workload for `max(request, usage)` of each. Capacity nobody requested is `__idle__` — the cluster-level
equivalent of an idle VM.

- Deploy: Argo CD `app-opencost.yaml` or the Flux HelmRelease (chart `opencost` 2.5.32), pointed at the
  Prometheus from `deploy/helm/monitoring-stack`.
- Alerts (`finops_rules.yml`): projected monthly cluster cost over budget (warning) and over 150% of it
  (critical), a >30% day-over-day spike, idle share above 40% for 12h, and namespaces whose cost doubled
  against their 7-day average. The monthly budget is the `finops:cluster_monthly_budget_usd` recording
  rule.
- Offline: `golden.finops.allocate_cluster_cost(nodes, pods)` implements the same model for capacity
  planning and tests; `share_idle=True` spreads idle cost back to namespaces for chargeback.

Namespaces should carry the same `team` / `cost-center` labels as cloud resources so OpenCost
allocations join the cloud showback.

## 9. Shift left: cost in the pull request

`.github/workflows/infracost.yml` runs on pull requests that change `deploy/terraform/**`. It prices
`deploy/terraform/live/aws/dev` on the base branch and on the PR, and posts (or updates) a comment with
the monthly cost difference. It needs the `INFRACOST_API_KEY` repository secret; without it the job
prints a notice and passes.

## 10. Operating cadence

| When | What |
|---|---|
| Every PR | Infracost diff; OPA tagging gate on the plan |
| Daily | Anomaly alerts (cloud-native + OpenCost rules); triage within one business day |
| Weekly | Top untagged resources from `tag_coverage()`; idle/rightsizing tickets to owning teams |
| Monthly | Showback (later chargeback) per team; unit cost trend; budget review; commitment sizing |
| Quarterly | Revisit required tags, shared-cost method and budgets with finance and engineering leads |
