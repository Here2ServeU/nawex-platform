# ------------------------------------------------------------------------------
# Cloud Identity personas — security/identity/gcp-access-model.yaml
#
#   persona.roles × assignment.scopes   -> role at folder / organization scope
#   assignment: binding                 -> google_folder_iam_member /
#                                          google_organization_iam_member (standing)
#   assignment: entitlement             -> google_privileged_access_manager_entitlement
#                                          (just-in-time, max_request_duration,
#                                          optional approval)
#   assignment.group                    -> existing Cloud Identity group synced from
#                                          AD by GCDS (looked up, never created here)
#   break-glass groups                  -> the only exception (with the deployer) to
#                                          the organization IAM deny policy
# ------------------------------------------------------------------------------

locals {
  persona_list = [for p in try(var.access_model.personas, []) : p if var.identity_enabled]
  domain       = coalesce(var.domain, try(var.access_model.identity_source.domain, "example.com"))

  personas = { for p in local.persona_list : p.name => p }

  groups = toset(flatten([
    for p in local.persona_list : [for a in try(p.assignments, []) : replace(a.group, "$${domain}", local.domain)]
  ]))

  grants = merge(flatten([
    for p in local.persona_list : [
      for a in try(p.assignments, []) : [
        for role in p.roles : {
          for scope in a.scopes : "${p.name}|${role}|${a.group}|${scope}" => {
            persona = p.name
            role    = role
            member  = "group:${replace(a.group, "$${domain}", local.domain)}"
            scope   = scope
          }
        }
      ] if try(p.assignment, "binding") == "binding"
    ]
  ])...)

  org_grants    = { for k, g in local.grants : k => g if g.scope == "organization" }
  folder_grants = { for k, g in local.grants : k => g if g.scope != "organization" }

  # One PAM entitlement per persona × scope, carrying all of the persona's roles.
  entitlement_groups = {
    for pair in flatten([
      for p in local.persona_list : [
        for a in try(p.assignments, []) : [
          for scope in a.scopes : {
            key    = "${p.name}|${scope}"
            member = "group:${replace(a.group, "$${domain}", local.domain)}"
          }
        ]
      ] if try(p.assignment, "binding") == "entitlement"
    ]) : pair.key => pair.member...
  }

  entitlements = {
    for k, members in local.entitlement_groups : k => {
      persona = split("|", k)[0]
      scope   = split("|", k)[1]
      members = distinct(members)
      roles   = local.personas[split("|", k)[0]].roles
      seconds = (
        tonumber(coalesce(regex("^PT(?:([0-9]+)H)?(?:([0-9]+)M)?$", local.personas[split("|", k)[0]].max_request_duration)[0], "0")) * 3600 +
        tonumber(coalesce(regex("^PT(?:([0-9]+)H)?(?:([0-9]+)M)?$", local.personas[split("|", k)[0]].max_request_duration)[1], "0")) * 60
      )
      require_approval = try(local.personas[split("|", k)[0]].require_approval, false)
    }
  }

  break_glass_groups = distinct(flatten([
    for p in local.persona_list : [
      for a in try(p.assignments, []) : replace(a.group, "$${domain}", local.domain)
    ] if try(p.privileged, false)
  ]))
}

# GCDS-synced groups must already exist; a missing group fails the plan instead of
# granting access to an address nobody controls.
data "google_cloud_identity_group_lookup" "persona" {
  for_each = var.verify_groups ? local.groups : toset([])

  group_key {
    id = each.value
  }
}

resource "google_organization_iam_member" "persona" {
  for_each = local.org_grants

  org_id = var.org_id
  role   = each.value.role
  member = each.value.member

  depends_on = [data.google_cloud_identity_group_lookup.persona]
}

resource "google_folder_iam_member" "persona" {
  for_each = local.folder_grants

  folder = local.folder_ids[each.value.scope]
  role   = each.value.role
  member = each.value.member

  depends_on = [data.google_cloud_identity_group_lookup.persona]
}

resource "google_privileged_access_manager_entitlement" "persona" {
  for_each = local.entitlements

  entitlement_id       = substr(replace("${each.value.persona}-${each.value.scope}", "/[^a-z0-9-]/", "-"), 0, 63)
  location             = var.pam_location
  parent               = local.scope_name[each.value.scope]
  max_request_duration = "${each.value.seconds}s"

  eligible_users {
    principals = each.value.members
  }

  privileged_access {
    gcp_iam_access {
      resource      = "//cloudresourcemanager.googleapis.com/${local.scope_name[each.value.scope]}"
      resource_type = each.value.scope == "organization" ? "cloudresourcemanager.googleapis.com/Organization" : "cloudresourcemanager.googleapis.com/Folder"

      dynamic "role_bindings" {
        for_each = each.value.roles
        content {
          role = role_bindings.value
        }
      }
    }
  }

  requester_justification_config {
    unstructured {}
  }

  dynamic "approval_workflow" {
    for_each = each.value.require_approval ? [1] : []
    content {
      manual_approvals {
        require_approver_justification = true
        steps {
          approvals_needed = 1
          approvers {
            principals = var.pam_approvers
          }
        }
      }
    }
  }

  depends_on = [data.google_cloud_identity_group_lookup.persona]

  lifecycle {
    precondition {
      condition     = !each.value.require_approval || length(var.pam_approvers) > 0
      error_message = "A persona with require_approval: true needs var.pam_approvers."
    }
  }
}

# Everyone except break-glass and the deployer is denied the permissions that would
# let them weaken org-level security settings — even if an allow binding grants them.
resource "google_iam_deny_policy" "protect_security_settings" {
  count = var.identity_enabled && var.deny_policy_enabled ? 1 : 0

  name         = "protect-security-settings"
  parent       = urlencode("cloudresourcemanager.googleapis.com/${local.org}")
  display_name = "Protect org security settings (break-glass exempt)"

  rules {
    description = "Only break-glass and the IaC deployer may change custom roles, mint service-account keys or delete projects."
    deny_rule {
      denied_principals = ["principalSet://goog/public:all"]
      exception_principals = concat(
        [for g in local.break_glass_groups : "principalSet://goog/group/${g}"],
        var.deny_exception_principals,
      )
      denied_permissions = var.denied_permissions
    }
  }
}
