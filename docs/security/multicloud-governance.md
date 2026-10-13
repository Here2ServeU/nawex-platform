# Multi-cloud governance: AWS ↔ Azure ↔ GCP

AWS, Azure and GCP are governed with the same design:

- one persona model per cloud, with the same persona names in each;
- directory groups that are looked up and never created, so Active Directory stays the source of truth;
- preventive guardrails at the top of the resource hierarchy;
- administrator access only through a just-in-time break-glass persona.

The AWS design is described in [aws-iam-modernization.md](../modernization/aws-iam-modernization.md). This
page maps that design onto Azure and GCP.

## 1. Equivalence table

| Concern | AWS | Azure | GCP |
|---|---|---|---|
| Resource hierarchy | Organization root → OUs → accounts | Intermediate root management group → child MGs → subscriptions | Organization node → folders → projects |
| Preventive guardrails | SCPs (principals in the org), RCPs (anyone acting on org resources) | Azure Policy assignments at MG scope (`deny`, `deployIfNotExists`) | Organization Policy constraints (`google_org_policy_policy`) |
| Workforce identity | IAM Identity Center + PingFederate (SAML + SCIM) | Entra ID, groups synced from AD by Entra Connect | Cloud Identity, groups synced from AD by GCDS; SSO to PingFederate |
| Persona → access unit | Permission set (managed + inline policies) | Built-in role(s) at MG scope | Predefined role(s) at folder / org scope |
| Standing access | Account assignment | `azurerm_role_assignment` (`assignment: active`) | `google_folder_iam_member` / `google_organization_iam_member` (`assignment: binding`) |
| Time-bound access | Permission-set `session_duration` | PIM eligible assignment + activation policy (`activation_duration`, MFA, justification, approval) | Privileged Access Manager entitlement (`max_request_duration`, justification, approval) |
| Ceiling on delegated / self-granted rights | Permission boundary + `enforce-permission-boundary` SCP | Privileged roles (Owner, User Access Administrator, RBAC Administrator) kept to break-glass by the linter, behind PIM. Custom-role / ABAC constraints are the next step | IAM deny policy at the org (exceptions: break-glass + deployer) |
| Region control | `region-allowlist` SCP | *Allowed locations* policy | `constraints/gcp.resourceLocations` |
| No public exposure by default | RCP data perimeter | *Network interfaces should not have public IPs* (landing zones), *Secure transfer to storage accounts* (Deny) | `compute.vmExternalIpAccess` (deny all), `storage.uniformBucketLevelAccess`, `sql.restrictPublicIp` |
| No long-lived credentials | `deny-root-and-iam-users` SCP | Entra-only identities. Classic (ASM) resources denied by *Not allowed resource types* | `iam.disableServiceAccountKeyCreation` + deny on `serviceAccountKeys.create` |
| Identity-domain lock | RCP: org identities only | Entra tenant (guest access via Conditional Access) | `iam.allowedPolicyMemberDomains` = directory customer ID |
| Mandatory tagging | Tag policies / OPA `tagging.rego` | *Require a tag on resources* × `Team`, `CostCenter`, `Environment` | Labels: not enforced by this module; enforce in the project factory |
| Security services always on | `protect-security-services` SCP | *Enable Microsoft Defender for Cloud on your subscription* (`deployIfNotExists`, managed identity + role) | Security Command Center activation is outside this module; the deny policy protects IAM settings |
| Account / subscription / project vending | `modules/aws/account-vending` (or Control Tower AFT) | `subscription_placement` map into MGs | Projects with `folder_id = folder_ids[...]` |
| Model linter | `golden.identity.model` | `golden.identity.multicloud` | `golden.identity.multicloud` |

## 2. How the persona model maps

All three model files define the same nine personas: `read-only`, `security-auditor`, `security-engineer`,
`developer`, `platform-engineer`, `sre-oncall`, `network-admin`, `finops` and `break-glass`.
`golden.identity.multicloud.persona_matrix` checks that the three files stay aligned. It reports
`PERSONA_MISSING` when a persona exists in one cloud but not another, and `PRIVILEGE_MISMATCH` when a
persona is privileged in one cloud and not in another.

| Persona | AWS permission set | Azure role(s) · assignment | GCP role(s) · assignment |
|---|---|---|---|
| read-only | ReadOnly (`ViewOnlyAccess`) | Reader · active | `roles/viewer` · binding |
| security-auditor | SecurityAudit | Security Reader + Reader @ root · active | `iam.securityReviewer`, `securitycenter.adminViewer`, `viewer` @ org · binding |
| security-engineer | SecurityEngineer (boundary) | Security Admin @ root · eligible, PT4H | `securitycenter.admin` @ org · entitlement, PT4H |
| developer | Developer (`PowerUserAccess` + boundary) | Contributor in nonprod/sandbox · active; Reader in prod | run/container developer, Cloud Build, Artifact Registry writer · binding |
| platform-engineer | PlatformEngineer (boundary) | Contributor · eligible, PT4H (never standing in prod) | `container.admin`, `compute.admin`, `iam.serviceAccountUser` · entitlement, PT4H |
| sre-oncall | SREOnCall (`ReadOnlyAccess` + bounded ops) | Reader, VM Contributor, AKS Cluster User · eligible, PT4H | `viewer`, `container.developer`, `compute.instanceAdmin.v1` · entitlement, PT4H |
| network-admin | NetworkAdmin | Network Contributor @ platform · eligible, PT4H | `compute.networkAdmin`, `dns.admin` @ platform · entitlement, PT4H |
| finops | FinOps (`AWSBillingReadOnlyAccess`) | Cost Management Reader @ root · active | `billing.viewer` @ org · binding |
| break-glass | BreakGlassAdmin (`AdministratorAccess`, PT1H) | **Owner** @ root · eligible, PT1H, approval | **`roles/owner`** + `organizationAdmin` @ org · entitlement, PT1H, approval |

The linter applies the same rules to all three clouds:

| Rule | AWS (`model.py`) | Azure / GCP (`multicloud.py`) |
|---|---|---|
| Administrator access only on break-glass | `PRIVILEGED_POLICY` | `PRIVILEGED_ROLE` (Owner, UAA, RBAC Admin / `roles/owner`, org/folder admin, security admin, org-policy admin) |
| Privileged access is never standing | 1h session cap | `STANDING_PRIVILEGE`, `PRIVILEGED_WITHOUT_APPROVAL` |
| Bounded session / activation | `SESSION_TOO_LONG`, `PRIVILEGED_SESSION_TOO_LONG` | `ACTIVATION_TOO_LONG`, `PRIVILEGED_ACTIVATION_TOO_LONG`, `MISSING_DURATION`, `INVALID_DURATION` |
| Broad rights need a guard | `BROAD_POLICY_WITHOUT_BOUNDARY` | `STANDING_BROAD_ROLE_IN_PROD` (Contributor / `roles/editor`), `BASIC_ROLE` warning |
| Group naming | `GROUP_NAMING` (`AWS-…`) | `GROUP_NAMING` (`AZ-…` / `gcp-…@domain`) |
| Known targets only | `UNKNOWN_ACCOUNT_GROUP` | `UNKNOWN_SCOPE` |
| Top of hierarchy needs opt-in | `MANAGEMENT_ACCOUNT_ACCESS` (`allow_management`) | `ROOT_SCOPE_ACCESS` (`allow_root` / `allow_organization`) |

## 3. Rollout order

Roll out the same way on each cloud: identity first, guardrails in audit mode, then enforce, starting with
sandbox.

1. **Directory sync.** Create the `AZ-*` groups (Entra Connect) and `gcp-*@domain` groups (GCDS) in AD
   first. Both Terraform modules look groups up and fail the plan if one is missing.
2. **Lint.** Run `golden.identity.multicloud.multicloud_summary()`. It must report `valid: true` and an
   empty matrix finding list.
3. **Hierarchy.** Apply `live/azure/governance` and `live/gcp/org` with `identity_enabled = false`, then
   place subscriptions (`subscription_placement`) and create projects under `folder_ids`.
4. **Guardrails, audit first.**
   - Azure: `enforce_policies = false` (DoNotEnforce), with `policy_scope_overrides` pointing the deny
     assignments at `sandbox`.
   - GCP: list constraints in `dry_run_constraints` where the constraint supports dry run. Otherwise apply
     the constraint to the `sandbox` folder first.
   - Review compliance, then widen to nonprod, prod and finally root / org. This is the same staged
     rollout as the SCPs in [guardrail-rollout.md](../../ops/runbooks/identity/guardrail-rollout.md).
5. **Personas.** Set `identity_enabled = true`. Standing read access comes first, then PIM / PAM
   eligibility. Break-glass comes last, after `pim_approver_group` / `pam_approvers` are set and an
   activation has been tested end to end.
6. **Deny policy (GCP).** Add the Terraform deployer to `deny_exception_principals` before enabling it,
   or the next apply will lock itself out of custom roles.
7. **AWS accounts.** New accounts come from `modules/aws/account-vending`. Its `account_groups` output
   feeds `live/aws/org` `account_groups`, so personas reach a new account on the next identity apply.

## 4. Operating notes and limits

- **Azure break-glass.** PIM-eligible Owner covers normal emergencies. You still need two cloud-only
  emergency-access accounts that are excluded from Conditional Access, because PIM itself depends on
  Entra ID being available. Those accounts are managed outside this model.
- **One PIM policy per role and scope.** `azurerm_role_management_policy` applies to every eligible
  assignment of that role at that MG, including assignments made outside Terraform. When two personas
  share a role at the same scope, the module applies the shortest `activation_duration` and requires
  approval if either persona does.
- **Policy definition IDs.** The module references built-in definitions by GUID, with the display name in
  a comment. Check them with `az policy definition show --name <guid>`. Override an ID through
  `policy_definition_ids` if Microsoft re-versions a definition. The Defender DINE identity gets
  `defender_remediation_role` (default *Security Admin*), which must match the definition's
  `roleDefinitionIds`.
- **GCP deny-policy permissions.** Deny policies accept only permissions on Google's *supported in deny
  policies* list, written in `service.googleapis.com/resource.verb` form. The defaults cover custom roles,
  service-account key creation and project deletion. Organization-policy changes are protected because
  `roles/orgpolicy.policyAdmin` is a privileged role that the linter allows only on break-glass.
- **PAM and basic roles.** If your organization doesn't allow `roles/owner` in a PAM entitlement, replace
  it in `gcp-access-model.yaml` with `roles/resourcemanager.organizationAdmin` + `roles/iam.securityAdmin`.
  The linter still treats both as privileged.
- **Control Tower AFT.** Account Factory for Terraform is the managed alternative to
  `modules/aws/account-vending`. Use AFT when Control Tower owns the landing zone, and the module when
  Organizations is managed directly with Terraform. Never manage the same account with both.

## 5. Files

| Piece | Location |
|---|---|
| Azure persona model | `security/identity/azure-access-model.yaml` |
| GCP persona model | `security/identity/gcp-access-model.yaml` |
| AWS persona model | `security/identity/access-model.yaml` |
| Azure MGs, Policy, Entra roles + PIM | `deploy/terraform/modules/azure/governance` → `deploy/terraform/live/azure/governance` |
| GCP folders, Org Policy, IAM, PAM, deny policy | `deploy/terraform/modules/gcp/org-governance` → `deploy/terraform/live/gcp/org` |
| AWS account vending | `deploy/terraform/modules/aws/account-vending` |
| AWS SCP/RCP, Identity Center, boundary | `deploy/terraform/modules/aws/{org-guardrails,identity-center,permission-boundary}` → `deploy/terraform/live/aws/org` |
| Linter + cross-cloud matrix | `src/golden/identity/multicloud.py` (tests: `tests/test_identity_multicloud.py`) |
| Threat model (cloud IAM section) | `security/threat-models/platform-stride.md` |
