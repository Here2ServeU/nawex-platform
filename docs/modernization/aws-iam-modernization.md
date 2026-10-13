# AWS IAM Modernization — Identity Center, SCPs/RCPs, Permission Boundaries

How to move an AWS estate from per-account IAM users and SAML roles to **persona-based access through
IAM Identity Center**, with the right guardrail at the right layer. You can rerun every step, review it
in Git and measure the result. Phases and roles follow the [modernization playbook](./README.md).

Platform pieces used here:

| Piece | Location |
|---|---|
| Persona access model (the one file you design in) | `security/identity/access-model.yaml` |
| Permission sets + AD/SCIM group assignments | `deploy/terraform/modules/aws/identity-center` |
| SCPs + RCPs (policy JSON templates) | `deploy/terraform/modules/aws/org-guardrails/policies/{scp,rcp}/` |
| Permission boundary (every role) | `deploy/terraform/modules/aws/permission-boundary` (wired into EKS + `live/aws/{dev,staging,prod}`) |
| Wiz read-only connector role | `deploy/terraform/modules/aws/wiz-connector` |
| Org-level root (management / delegated admin) | `deploy/terraform/live/aws/org` |
| Plan-time policy gate (OPA) | `security/policies/opa/aws-iam.rego` · `scripts/iam-policy-gate.sh` |
| Model lint, role cleanup, Wiz gap assessment | `golden iam model\|roles\|gaps\|controls`; service `identity-governance` :8098 |
| Alerts | `observability/prometheus/rules/identity_rules.yml` |
| Rollout + break-glass runbook | [ops/runbooks/identity/guardrail-rollout.md](../../ops/runbooks/identity/guardrail-rollout.md) |

## 1. Target architecture

```text
 Active Directory ──(AD connector / LDAP)──▶ PingFederate ──SAML 2.0 (SSO, MFA)──▶ IAM Identity Center
   groups  AWS-<Persona>                         │                                   │
                                                 └──SCIM 2.0 (users + groups)────────┘
                                                                                     │ assignment:
                                                       group × permission set × account (Terraform)
                                                                                     ▼
 ┌─────────── AWS Organization ───────────────────────────────────────────────────────────────────┐
 │  SCPs  (what principals in the org may do)  deny-root-and-iam-users · enforce-permission-boundary │
 │                                             protect-security-services · region-allowlist        │
 │  RCPs  (who may touch org resources)        data-perimeter: org identities · confused deputy · TLS│
 │  ┌ OU sandbox ┐ ┌ OU nonprod ┐ ┌ OU prod ┐ ┌ OU security / shared / network ┐                     │
 │  every role: permissions_boundary = golden-workload-boundary                                    │
 └─────────────────────────────────────────────────────────────────────────────────────────────────┘
        ▲ Terraform plan ─▶ OPA aws-iam.rego (deny/warn) ─▶ apply          ▲ Wiz connector (read-only)
                                                                          └─▶ issues export ─▶ golden iam gaps
```

**Identity source.** Active Directory stays the system of record for people and group membership.
PingFederate is the external IdP for IAM Identity Center. It handles SAML for sign-in, enforces MFA in
its authentication policy, and provisions users and groups over SCIM. Terraform **looks up** the
SCIM-provisioned groups (`aws_identitystore_group`) and never creates them, so a missing AD group
fails the plan rather than producing an empty, unmanaged group.

## 2. Control placement

Place each control at the earliest layer that can enforce it reliably. Add detective coverage behind
it so you can see when it fails. The catalog lives in `src/golden/identity/controls.py`; `golden iam
controls` prints it, and tests assert that every artifact it references exists.

| Control | Pipeline (OPA) | Org (SCP) | Resource (RCP) | Boundary | Access design | Detective (Wiz) | IdP |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| IAM-01 Root user locked down | | ● | | | | ● | |
| IAM-02 No long-lived IAM user credentials | ● | ● | | ● | | ● | |
| IAM-03 Permission boundary on every role | ● | ● | | ● | | | |
| IAM-04 Least privilege, no standing admin | ● | | | | ● | ● | |
| IAM-05 Workforce access only via Identity Center | | | | | ● | ● | |
| IAM-06 Phishing-resistant MFA | | | | | | | ● |
| IAM-07 Hardened cross-account trust | ● | | ● | | | ● | |
| IAM-08 Unused roles/credentials removed | | | | | ● | ● | |
| IAM-09 Bounded session duration | ● | | | | ● | | |
| DP-01 Data perimeter (org identities only) | | | ● | | | ● | |
| DP-02 Encryption in transit | | | ● | | | | |
| GOV-01 Security services can't be disabled | | ● | | ● | | | |
| GOV-02 Region allow-list | | ● | | | | | |
| GOV-03 Policy-as-code gate on IAM changes | ● | | | | | | |
| DET-01 Continuous posture assessment | | | | | | ● | |

What each layer can and cannot do:

- **SCPs** cap the permissions of principals in member accounts. They don't apply to the management
  account or to service-linked roles. Only `Deny` statements are used, and each is exempted for break-glass
  and the IaC deployer through `exempt_principal_arns`, never through `*`.
- **RCPs** cap what *any* principal, including ones outside the org, can do to S3, SQS, KMS, Secrets
  Manager and STS resources. They need `Principal: "*"`. Tag a resource `dp:exclude:identity=true` to make
  a sanctioned exception.
- **Permission boundaries** let teams create their own roles (`delegated_iam: true`) without being able
  to escalate. The `enforce-permission-boundary` SCP and the `aws-iam.rego` plan check make the boundary
  mandatory.
- **OPA** runs before anything reaches AWS. It also enforces what no SCP can express: session-duration
  limits, admin policies only on `BreakGlassAdmin`, no `Allow` + `NotAction`, and the 5,120-character SCP
  size limit.

## 3. Persona-based access

`security/identity/access-model.yaml` defines every persona in one place:

- the permission set it becomes;
- its session length;
- its policies, as AWS-managed names, customer-managed policies and inline statements;
- whether it carries the boundary, and whether it may create bounded roles;
- the **AD groups** that receive it, and in which **account groups**.

Account groups are logical names (`workloads-prod`, `sandbox`, …). Each organization maps them to
account IDs in `live/aws/org/terraform.tfvars`, so the model is portable and holds no account IDs.

| Persona | Permission set | Session | Boundary | AD group → account groups |
|---|---|---|---|---|
| read-only | ReadOnly | 8h | | AWS-ReadOnly → all workload accounts; AWS-Developers → prod |
| security-auditor | SecurityAudit | 8h | | AWS-SecurityAudit → all incl. management |
| security-engineer | SecurityEngineer | 4h | ● | AWS-SecurityEngineering → security |
| developer | Developer (PowerUser + delegated IAM) | 8h | ● | AWS-Developers → nonprod, sandbox |
| platform-engineer | PlatformEngineer (PowerUser + delegated IAM) | 4h | ● | AWS-PlatformEngineering → shared, prod, nonprod |
| sre-oncall | SREOnCall (ReadOnly + bounded ops) | 4h | ● | AWS-SRE → prod, nonprod |
| network-admin | NetworkAdmin | 4h | ● | AWS-NetworkAdmins → network |
| finops | FinOps | 8h | | AWS-FinOps → management |
| break-glass | BreakGlassAdmin (AdministratorAccess) | 1h | | AWS-BreakGlass (empty; PAM-granted) → all |

`golden iam model` lints the design before a plan. It checks for:

- privileged policies on everyday personas;
- PowerUser access or delegated IAM without a boundary;
- sessions longer than 8h, or 1h for privileged personas;
- AD groups outside `^AWS-…$`;
- unknown account groups;
- management-account assignments without `allow_management`;
- wildcard inline statements.

```bash
make iam-model                    # lint + AD group → permission set map
```

## 4. Engagement phases

### Phase 1 — Discover (week 1–2)

```bash
# Per account (or loop over the org with an audit role):
aws iam get-account-authorization-details --output json > details-<account>.json
# Combine into [{"account_id": "...", "details": {...}}, ...] and analyze:
golden iam roles --input estate.json --org-accounts 111111111111,222222222222 --verbose > roles.json
# Wiz: Issues → Export CSV (or the GraphQL `issues` query) and assess:
golden iam gaps --wiz wiz-issues.csv --verbose > gaps.json
```

`golden iam roles` gives every customer role a disposition:

- **remove**: unused for 90 days or never used. Deleting it is the governed `delete_iam_role` action
  and needs a named approver.
- **migrate_to_permission_set**: a direct PingFederate→IAM SAML role. The output names the closest
  persona by policy overlap. It never suggests break-glass.
- **consolidate**: the same permissions, boundary and trusted principals as another role in the
  account. The output says which role to keep.
- **remediate**: admin access, open or unguarded cross-account trust, or no boundary.
- **keep**: nothing to do.

The summary reports the role-reduction percentage and boundary coverage. These are the two numbers
leadership tracks.

`golden iam gaps` maps every open Wiz finding onto the control catalog. Each control comes out as
`effective`, `partial` or `gap`, along with its affected accounts, an identity posture score and the
remediation for the layer where the control lives. Findings outside identity scope, such as CVEs or EBS
encryption, are listed separately so nothing is silently dropped.

### Phase 2 — Design (week 2–4)

1. Workshop personas with each team. Edit `access-model.yaml` and run `make iam-model`.
2. In AD, create one group per persona assignment (`AWS-<Persona>`). Scope the PingFederate SCIM
   connection to `AWS-*` groups only.
3. In PingFederate, add an SP connection for IAM Identity Center:
   - Import the Identity Center SAML metadata.
   - Set `NameID` to the user's email or UPN, matching the SCIM `userName`.
   - Apply an authentication policy that requires MFA (PingID / FIDO2).
   - Enable outbound SCIM provisioning with the Identity Center SCIM endpoint and bearer token. Rotate
     the token before its one-year expiry.
4. Agree the `exempt_principal_arns` list, which should be break-glass and the deployer role only, and the
   allowed regions.

### Phase 3 — Build guardrails (week 3–5)

```bash
cp deploy/terraform/live/aws/org/terraform.tfvars.example deploy/terraform/live/aws/org/terraform.tfvars
$EDITOR deploy/terraform/live/aws/org/terraform.tfvars   # account_groups, scp_targets, rcp_targets
make iam-plan                                            # terraform plan + OPA gate (deny fails the run)
terraform -chdir=deploy/terraform/live/aws/org apply
```

Prerequisites in the management account (a one-off, usually owned by the landing-zone team):

- All features enabled.
- `SERVICE_CONTROL_POLICY` and `RESOURCE_CONTROL_POLICY` policy types enabled on the root.
- Identity Center enabled, with the external IdP set to PingFederate and automatic SCIM provisioning on.
- The delegated administrator for Identity Center registered.

Deploy `modules/aws/permission-boundary` and `modules/aws/wiz-connector` to every member account,
from the account baseline or a StackSet. The `live/aws/{dev,staging,prod}` landing zones already create
the boundary and attach it to every EKS and IRSA role.

### Phase 4 — Migrate access and clean up (week 5–10)

Work OU by OU, sandbox → nonprod → prod, following
[guardrail-rollout.md](../../ops/runbooks/identity/guardrail-rollout.md):

1. Add the users to the new AD groups, wait for SCIM, and confirm they can sign in through the access
   portal.
2. Remove them from the legacy `PingFed-*` SAML roles, then delete those roles and the per-account SAML
   provider. The `protect-security-services` SCP blocks SAML provider changes for everyone except the
   exempt principals, so a rogue IdP can't be added back.
3. Backfill `golden-workload-boundary` on the roles `golden iam roles` flags as `NO_BOUNDARY`, and
   **then** attach `enforce-permission-boundary` to that OU.
4. Delete the `remove` roles and merge the `consolidate` roles. Retire IAM users.

### Phase 5 — Operate (continuous)

- **Every IAM change** runs `scripts/iam-policy-gate.sh <terraform dir>`. `make iam-plan` does this for the
  org stack; add the same step to any pipeline that plans AWS Terraform.
- **Nightly**: export authorization details and Wiz issues, then POST them to `identity-governance`
  (`/api/v1/identity/roles/analyze`, `/api/v1/identity/gap-assessment`). The gauges feed
  `identity_rules.yml`, which covers open-trust roles, lingering IAM users, boundary coverage and
  control gaps.
- **Quarterly**: run an access review per persona, which comes down to AD group membership. Rerun
  `golden iam gaps` and report the posture score trend.

## 5. Policy gate reference (`aws-iam.rego`)

| Rule | Result |
|---|---|
| `aws_iam_role` without the workload boundary (unless only known after apply) | deny |
| `aws_iam_user`, `aws_iam_access_key`, `aws_iam_user_login_profile` | deny |
| `Allow` `Action:*` on `Resource:*` in a policy, inline role policy or permission-set inline policy (the boundary policy itself is exempt) | deny |
| `Allow` with `NotAction` | deny |
| `AdministratorAccess` / `IAMFullAccess` attached to a role or group | deny |
| Trust policy allowing `AWS: "*"` with no condition | deny |
| Permission-set session > 8h, or > 1h on `BreakGlassAdmin` | deny |
| Admin managed policy on any permission set but `BreakGlassAdmin` | deny |
| SCP/RCP content > 5,120 characters | deny |
| Cross-account trust without `sts:ExternalId` / `aws:PrincipalOrgID` | warn |
| Deleting an Organizations policy or attachment | warn |

```bash
make iam-policy-test                                     # opa check --strict + opa test
scripts/iam-policy-gate.sh deploy/terraform/live/aws/dev # gate any root
scripts/iam-policy-gate.sh --plan-json plan.json         # gate a plan from another pipeline
```

## 6. API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/identity/access-model` | Loaded model, AD group map and lint result (`GOLDEN_ACCESS_MODEL`) |
| POST | `/api/v1/identity/access-model/lint` | Lint a proposed model |
| POST | `/api/v1/identity/roles/analyze` | `{"accounts": [{"account_id", "details"}], "unused_days", "org_accounts"}` |
| POST | `/api/v1/identity/gap-assessment` | `{"findings": [...]}` (Wiz CSV rows or GraphQL issue nodes) |
| GET | `/api/v1/identity/controls` | Control-placement catalog |
| GET | `/api/v1/identity/sample-authorization-details` · `/sample-findings` | Demo data |

The service only analyzes and recommends. It never calls AWS. Changes go through Terraform, and the
cleanup actions are in the ActionGovernor catalog. `delete_iam_role` is critical, so it always needs a
named human approver. `quarantine_iam_role` is high risk, so it needs approval in `supervised` mode.
