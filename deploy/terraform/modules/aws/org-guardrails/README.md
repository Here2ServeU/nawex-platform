# org-guardrails

SCPs and RCPs for the AWS organization. Each policy is a JSON template under `policies/`, rendered
with the organization ID, partition, allowed regions, boundary name and exempt principals, then minified.

| Policy | Type | Effect |
|---|---|---|
| `deny-root-and-iam-users` | SCP | Denies the root user, IAM users, access keys and console passwords, and leaving the org |
| `enforce-permission-boundary` | SCP | Role creation and policy edits require `golden-workload-boundary`; the boundary can't be removed or edited |
| `protect-security-services` | SCP | Protects CloudTrail, Config, GuardDuty, Security Hub, Access Analyzer, Inspector, Macie and SAML/OIDC providers |
| `region-allowlist` | SCP | Denies regional services outside `allowed_regions` (global services exempt) |
| `data-perimeter` | RCP | S3/SQS/KMS/Secrets Manager/STS: org identities only, confused-deputy protection, TLS only |

Prerequisites: all-features Organizations, with `SERVICE_CONTROL_POLICY` and `RESOURCE_CONTROL_POLICY`
enabled on the root. Run from the management account or the delegated administrator.

Attach per OU through `scp_targets` / `rcp_targets`, following
`ops/runbooks/identity/guardrail-rollout.md`. `tests/test_identity.py` renders every template and
checks that it's valid JSON, deny-only and within the 5,120-character limit.
