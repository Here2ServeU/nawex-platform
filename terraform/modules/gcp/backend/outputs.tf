# ------------------------------------------------------------------------------
# BOOTSTRAP OUTPUTS
# ------------------------------------------------------------------------------
# Purpose: Provides the configuration needed to migrate local state to remote GCS.
# ------------------------------------------------------------------------------

output "bucket_name" {
  description = "The globally unique name of the GCS state bucket"
  value       = google_storage_bucket.tfstate.name
}

output "bucket_location" {
  value = google_storage_bucket.tfstate.location
}

# Principal Touch: Generate the code block for the user
# This prevents typos when configuring the backend in the next step.
output "backend_config_instruction" {
  description = "Copy this block into your terraform/live/gcp/dev/main.tf"
  value       = <<EOT
  # ----------------------------------------------------------------
  # PASTE THIS INTO YOUR main.tf TO ENABLE REMOTE STATE
  # ----------------------------------------------------------------
  backend "gcs" {
    bucket  = "${google_storage_bucket.tfstate.name}"
    prefix  = "terraform/state/dev" 
  }
  EOT
}
