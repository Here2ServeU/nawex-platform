# Runbook: AWS Guardrail Rollout, Access Migration and Break-Glass

| | |
|---|---|
| **Applies to** | `deploy/terraform/live/aws/org` (SCPs, RCPs, Identity Center) and the member-account boundary |
| **Owner** | Cloud security architect (R), CISO delegate (A), platform + app team leads (C) |
| **Alerts** | `IdentityOpenTrustRole`, `IdentityIamUsersPresent`, `IdentityBoundaryCoverageLow`, `IdentityControlGaps` |
| **Background** | [docs/modernization/aws-iam-modernization.md](../../../docs/modernization/aws-iam-modernization.md) |

Guardrails are attached **one OU at a time**, in this order: sandbox → nonprod → prod → shared,
network and security. Stay on each OU for at least one full business week before moving to the next.

## 1. Before each OU

1. Get fresh evidence for the OU's accounts:

   ```bash
   golden iam roles --input estate.json --org-accounts "$(cat org-accounts.txt)" --verbose > roles.json
   jq '[.roles[] | select(.account_id as $a | $OU_ACCOUNTS | index($a)) | select(.disposition != "managed")
        | select(any(.findings[]; .code == "NO_BOUNDARY"))] | length' roles.json
   ```

2. **Gate:** the `NO_BOUNDARY` count for the OU must be **0** before you attach
   `enforce-permission-boundary`. Otherwise existing pipelines can no longer attach policies to their
   roles. To backfill, add `permissions_boundary` in the owning Terraform, or for unmanaged roles run
   `aws iam put-role-permissions-boundary --role-name <r> --permissions-boundary arn:aws:iam::<acct>:policy/golden-workload-boundary`.
3. Check the exempt list (`exempt_principal_arns`). It should contain only the break-glass permission
   set and `golden-terraform-deployer`.
4. Get the change ticket approved, then announce the window in the platform and app channels.

## 2. Attach

```bash
$EDITOR deploy/terraform/live/aws/org/terraform.tfvars   # add the OU ID to scp_targets / rcp_targets
make iam-plan                                            # OPA gate must report no DENY
terraform -chdir=deploy/terraform/live/aws/org apply
```

Attach in this order within an OU. Each step is independently reversible.

1. `deny-root-and-iam-users`, `protect-security-services`: low blast radius.
2. `region-allowlist`: check Cost Explorer for spend in non-allowed regions first.
3. `data-perimeter` RCP: tag sanctioned third-party buckets and keys `dp:exclude:identity=true` first.
4. `enforce-permission-boundary`: only after the gate in step 1.2.

## 3. Verify (first 48h)

- Watch CloudTrail for `errorCode = AccessDenied` with `explicit deny in a service control policy` or
  `resource control policy`, grouped by principal:

  ```sql
  -- CloudTrail Lake
  SELECT userIdentity.arn, eventSource, eventName, count(*) FROM <event_data_store>
  WHERE errorCode = 'AccessDenied' AND errorMessage LIKE '%control policy%' AND eventTime > now() - interval '1' day
  GROUP BY 1, 2, 3 ORDER BY 4 DESC
  ```

- A denial from a legitimate workload means something is missing from the boundary. Fix it in the
  owning Terraform. **Never** fix it by widening `exempt_principal_arns`.
- Rerun `golden iam gaps` with a fresh Wiz export. The controls for this OU should move to `effective`
  or `partial`.

## 4. Roll back

Remove the OU ID from the relevant `scp_targets` / `rcp_targets` entry and apply. The OPA gate warns
on guardrail removal, and the warning plus the change ticket are your audit evidence. If Terraform
itself is unavailable, the break-glass role can detach the policy in the console:
Organizations → Policies → *policy* → Targets → Detach.

## 5. Migrate a team from SAML roles to Identity Center

1. Check that the team's AD groups exist and are SCIM-synced:
   `aws identitystore list-groups --identity-store-id <id> --filters AttributePath=DisplayName,AttributeValue=AWS-Developers`.
2. Apply the org stack so the assignments exist. Users sign in through the access portal and confirm
   parity with their old role, using the `suggested_persona` from `golden iam roles`.
3. Remove the legacy SAML role from the PingFederate connection. Delete the IAM role, and once no roles
   reference it, delete the per-account SAML provider. Delete through the owning Terraform, or with
   `aws iam delete-role` for unmanaged roles, only after the owner signs off on the change ticket. Any
   automation that wires role cleanup into the AIOps loop must go through the governed
   `delete_iam_role` action (critical). That action waits in `GET /v1/actions/pending` until a named
   approver releases it with `POST /v1/actions/{id}/approve`.

## 6. Break-glass

The `AWS-BreakGlass` AD group is **empty**. To use it:

1. Open a P1 or a pre-approved emergency change. Your PAM tool or IdP admin adds the responder to
   `AWS-BreakGlass` for at most 1 hour. SCIM syncs within minutes.
2. The responder signs in through the access portal, picks `BreakGlassAdmin` (session limit 1h), does
   the minimum needed and records the actions in the incident ticket.
3. Remove the responder from the group. A security engineer reviews CloudTrail for the
   `AWSReservedSSO_BreakGlassAdmin_*` session and attaches the evidence to the incident.
4. If Identity Center or PingFederate itself is down, use the sealed root-credential procedure for the
   management account. The root user is denied in every member account by `deny-root-and-iam-users`.
