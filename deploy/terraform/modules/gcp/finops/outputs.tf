output "budget_alerts_topic" {
  description = "Pub/Sub topic receiving every budget update (subscribe automation here)."
  value       = google_pubsub_topic.budget_alerts.id
}

output "budget_ids" {
  description = "Budget display name -> budget resource name."
  value = merge(
    { (google_billing_budget.monthly.display_name) = google_billing_budget.monthly.name },
    { for b in google_billing_budget.team : b.display_name => b.name },
  )
}

output "billing_export_dataset" {
  description = "BigQuery dataset to select in Billing > Billing export (null when disabled)."
  value       = var.enable_billing_export_dataset ? google_bigquery_dataset.billing_export[0].dataset_id : null
}

output "project_number" {
  description = "Number of the hosting project."
  value       = data.google_project.this.number
}

output "required_labels" {
  description = "Required label keys, for org policy custom constraints and the OPA tagging gate."
  value       = var.required_labels
}
