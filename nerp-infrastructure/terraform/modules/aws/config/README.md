# AWS Config Module

Enables AWS Config with a delivery channel and recorder status.

## Usage
```hcl
module "config" {
  source = "../../../modules/aws/config"
  name = "aiops-config"
  bucket_name = "aiops-config-logs"
  create_bucket = true
  tags = {
    Environment = "dev"
  }
}
```

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
