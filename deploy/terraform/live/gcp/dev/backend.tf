# Partial backend configuration: supply the rest with
#   terraform init -backend-config=backend.hcl   (see backend.hcl.example)
# CI validates with `terraform init -backend=false`.
terraform {
  backend "gcs" {}
}
