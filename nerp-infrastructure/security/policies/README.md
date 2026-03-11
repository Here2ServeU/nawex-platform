# Security Policies

This folder stores policy-as-code and security governance artifacts.

## Files
- `policy-controls.md`: Required controls and enforcement levels.
- `opa/k8s-security.rego`: Kubernetes security policy baseline.
- `validate-policies.sh`: Quick local validator for policy files.

## Policy Areas
- Container hardening (`runAsNonRoot`, no privileged containers).
- Network isolation defaults.
- Secrets handling and rotation policy.
- Audit logging and retention requirements.

## Run Validation
```bash
bash security/policies/validate-policies.sh
```
