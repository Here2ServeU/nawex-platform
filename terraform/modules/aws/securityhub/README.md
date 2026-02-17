# AWS SecurityHub Module

Enables AWS SecurityHub and optional standards subscriptions.

## Usage
```hcl
module "securityhub" {
  source  = "../../../modules/aws/securityhub"
  enabled = true
  standards_arns = [
    "arn:aws:securityhub:::standards/aws-foundational-security-best-practices/v/1.0.0"
  ]
}
```
