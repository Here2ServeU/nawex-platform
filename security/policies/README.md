# Security Policies

This folder stores policy-as-code and security governance artifacts.

## Files
- `policy-controls.md`: Required controls and enforcement levels.
- `opa/k8s-security.rego`: Kubernetes security policy baseline.
- `opa/aws-iam.rego`: AWS IAM guardrails for Terraform plans (boundaries, no IAM users, no wildcard
  admin, trust policies, permission-set sessions, SCP size). Run it with `scripts/iam-policy-gate.sh <tf dir>`.
- `opa/tagging.rego`: required cost-allocation tags/labels on AWS, Azure and GCP resources in Terraform plans.
- `opa/network.rego`: no internet-exposed admin ports, no public database subnets, flow logs and WAF warnings.
- `kyverno/`: admission policies — keyless cosign signature + SBOM attestation required for platform
  images, no `:latest`, required labels.
- `validate-policies.sh`: Quick local validator for policy files.

## Policy Areas
- Container hardening (`runAsNonRoot`, no privileged containers).
- Network isolation defaults.
- Secrets handling and rotation policy.
- Audit logging and retention requirements.
- AWS IAM: mandatory permission boundaries, no long-lived credentials, admin only through break-glass.

## Run Validation
```bash
bash security/policies/validate-policies.sh
```
