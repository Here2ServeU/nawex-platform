output "folder_ids" {
  description = "Folder key (access-model scope) -> folders/<id>; feed project factories with these."
  value       = local.folder_ids
}

output "org_policy_constraints" {
  description = "Constraints managed at the organization."
  value       = keys(google_org_policy_policy.this)
}

output "binding_count" {
  description = "Standing role x group x scope bindings."
  value       = length(google_organization_iam_member.persona) + length(google_folder_iam_member.persona)
}

output "entitlements" {
  description = "PAM entitlement key (persona|scope) -> entitlement name."
  value       = { for k, e in google_privileged_access_manager_entitlement.persona : k => e.name }
}

output "deny_policy" {
  description = "Organization IAM deny policy name (null when disabled)."
  value       = try(google_iam_deny_policy.protect_security_settings[0].name, null)
}
