# SecurityHub + Config Enablement Playbook

## When to Use
- Initial cloud onboarding.
- Annual compliance refresh.
- After major architecture changes.

## Steps (Terraform)
1. Enable SecurityHub:
```hcl
module "securityhub" {
  source = "../../../modules/aws/securityhub"
  enabled = true
}
```
2. Enable AWS Config:
```hcl
module "config" {
  source = "../../../modules/aws/config"
  name = "aiops-config"
  bucket_name = "aiops-config-logs"
  create_bucket = true
}
```
3. Apply and verify:
- Confirm `SecurityHub` is enabled in the AWS console.
- Confirm `Config Recorder` is recording in the target region.

## Evidence
- Export SecurityHub findings summary.
- Capture Config recorder status and delivery channel output.
- Store evidence in the audit log repository.

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
