# ------------------------------------------------------------------------------
# Entra ID personas — security/identity/azure-access-model.yaml
#
#   persona.roles × assignment.scopes   -> built-in role at management-group scope
#   assignment: active                  -> azurerm_role_assignment (standing)
#   assignment: eligible                -> azurerm_pim_eligible_role_assignment +
#                                          azurerm_role_management_policy
#                                          (activation_duration, MFA, justification,
#                                           approval, eligibility expiry)
#   assignment.group                    -> existing Entra security group synced from
#                                          AD by Entra Connect (looked up, never
#                                          created here, so AD stays the source of
#                                          truth — same rule as the AWS module)
# ------------------------------------------------------------------------------

locals {
  persona_list = [for p in try(var.access_model.personas, []) : p if var.identity_enabled]
  personas     = { for p in local.persona_list : p.name => p }

  groups = toset(flatten([
    for p in local.persona_list : [for a in try(p.assignments, []) : a.group]
  ]))

  grants = merge(flatten([
    for p in local.persona_list : [
      for a in try(p.assignments, []) : [
        for role in p.roles : {
          for scope in a.scopes : "${p.name}|${role}|${a.group}|${scope}" => {
            persona  = p.name
            role     = role
            group    = a.group
            scope    = scope
            eligible = try(p.assignment, "active") == "eligible"
          }
        }
      ]
    ]
  ])...)

  active_grants   = { for k, g in local.grants : k => g if !g.eligible }
  eligible_grants = { for k, g in local.grants : k => g if g.eligible }

  # Activation duration in minutes (ISO-8601 PT#H#M), for picking the strictest
  # window when two personas share a role at the same scope.
  activation_minutes = {
    for name, p in local.personas : name => (
      tonumber(coalesce(regex("^PT(?:([0-9]+)H)?(?:([0-9]+)M)?$", p.activation_duration)[0], "0")) * 60 +
      tonumber(coalesce(regex("^PT(?:([0-9]+)H)?(?:([0-9]+)M)?$", p.activation_duration)[1], "0"))
    ) if try(p.activation_duration, null) != null
  }

  # One PIM policy per role × scope (Azure allows exactly one).
  pim_policy_members = {
    for k, g in local.eligible_grants : "${g.role}|${g.scope}" => g.persona...
  }
  pim_policies = {
    for k, personas in local.pim_policy_members : k => {
      role             = split("|", k)[0]
      scope            = split("|", k)[1]
      minutes          = min([for p in personas : lookup(local.activation_minutes, p, 480)]...)
      require_approval = anytrue([for p in personas : try(local.personas[p].require_approval, false)])
    }
  }
}

data "azuread_group" "persona" {
  for_each = local.groups

  display_name     = each.value
  security_enabled = true
}

data "azuread_group" "approver" {
  count = var.identity_enabled && var.pim_approver_group != null ? 1 : 0

  display_name     = var.pim_approver_group
  security_enabled = true
}

# Role definition IDs must be scope-qualified for PIM resources.
data "azurerm_role_definition" "pim" {
  for_each = local.pim_policies

  name  = each.value.role
  scope = local.mg_ids[each.value.scope]
}

resource "azurerm_role_assignment" "persona" {
  for_each = local.active_grants

  scope                = local.mg_ids[each.value.scope]
  role_definition_name = each.value.role
  principal_id         = data.azuread_group.persona[each.value.group].object_id
  principal_type       = "Group"
  description          = "golden persona ${each.value.persona} (azure-access-model.yaml)"
}

resource "azurerm_role_management_policy" "persona" {
  for_each = local.pim_policies

  scope              = local.mg_ids[each.value.scope]
  role_definition_id = data.azurerm_role_definition.pim[each.key].id

  activation_rules {
    maximum_duration                   = each.value.minutes % 60 == 0 ? "PT${floor(each.value.minutes / 60)}H" : "PT${floor(each.value.minutes / 60)}H${each.value.minutes % 60}M"
    require_multifactor_authentication = true
    require_justification              = true
    require_approval                   = each.value.require_approval

    dynamic "approval_stage" {
      for_each = each.value.require_approval ? [1] : []
      content {
        primary_approver {
          object_id = data.azuread_group.approver[0].object_id
          type      = "Group"
        }
      }
    }
  }

  eligible_assignment_rules {
    expiration_required = true
    expire_after        = "P${var.pim_eligibility_days}D"
  }

  # active_assignment_rules are left at the tenant default on purpose: standing
  # persona grants (assignment: active, e.g. Reader for read-only) are plain RBAC
  # assignments managed above, and the model linter keeps privileged roles and
  # Contributor-in-prod out of them.

  lifecycle {
    precondition {
      condition     = !each.value.require_approval || var.pim_approver_group != null
      error_message = "A persona with require_approval: true needs var.pim_approver_group."
    }
  }
}

resource "azurerm_pim_eligible_role_assignment" "persona" {
  for_each = local.eligible_grants

  scope              = local.mg_ids[each.value.scope]
  role_definition_id = data.azurerm_role_definition.pim["${each.value.role}|${each.value.scope}"].id
  principal_id       = data.azuread_group.persona[each.value.group].object_id
  justification      = "golden persona ${each.value.persona} (azure-access-model.yaml)"

  schedule {
    expiration {
      duration_days = var.pim_eligibility_days
    }
  }

  depends_on = [azurerm_role_management_policy.persona]

  lifecycle {
    # PIM recomputes the start time; re-certification happens by replacing the assignment.
    ignore_changes = [schedule[0].start_date_time]
  }
}
