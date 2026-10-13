# ------------------------------------------------------------------------------
# GCP ORG GOVERNANCE MODULE — folders, organization policy, Cloud Identity personas
# ------------------------------------------------------------------------------
# The GCP counterpart of modules/aws/org-guardrails + identity-center + the
# permission boundary:
#
#   AWS                                   GCP (this module)
#   Organization root / OUs           ->  organization node / folders
#   SCPs per OU                       ->  organization policy constraints
#   Identity Center permission sets   ->  predefined roles bound to Cloud Identity
#                                         groups at folder / org scope
#   session_duration (privileged)     ->  Privileged Access Manager entitlements
#   permission boundary / SCP deny    ->  IAM deny policy at the organization
#
# Hierarchy (keys are the scopes used in security/identity/gcp-access-model.yaml):
#
#   organization
#   ├── platform                 shared VPC host, logging, security tooling
#   ├── landing-zones
#   │   ├── landing-zones-prod
#   │   └── landing-zones-nonprod
#   ├── sandbox
#   └── decommissioned
#
# Projects are created by the project factory / landing-zone roots with
# folder_id = module.org_governance.folder_ids["<key>"].
# Run as an identity with Folder Admin, Organization Policy Administrator,
# Organization Administrator (IAM) and Deny Admin at the organization.
# ------------------------------------------------------------------------------

locals {
  org        = "organizations/${var.org_id}"
  top_level  = toset(["platform", "landing-zones", "sandbox", "decommissioned"])
  lz_level   = toset(["landing-zones-prod", "landing-zones-nonprod"])
  scope_name = merge({ "organization" = local.org }, local.folder_ids)

  display_names = {
    "platform"              = "Platform"
    "landing-zones"         = "Landing Zones"
    "landing-zones-prod"    = "Production"
    "landing-zones-nonprod" = "Non-production"
    "sandbox"               = "Sandbox"
    "decommissioned"        = "Decommissioned"
  }

  folder_ids = merge(
    { for k, f in google_folder.top : k => f.name },
    { for k, f in google_folder.landing_zones : k => f.name },
  )
}

# ------------------------------------------------------------------ hierarchy
resource "google_folder" "top" {
  for_each = local.top_level

  display_name = "${var.folder_prefix} ${local.display_names[each.key]}"
  parent       = local.org
}

resource "google_folder" "landing_zones" {
  for_each = local.lz_level

  display_name = "${var.folder_prefix} ${local.display_names[each.key]}"
  parent       = google_folder.top["landing-zones"].name
}

# ------------------------------------------------------------------ org policy
locals {
  # kind: boolean (enforce) | allow (allowed_values) | deny_all
  org_policies = {
    "gcp.resourceLocations"                = { kind = "allow", values = var.allowed_locations }
    "iam.allowedPolicyMemberDomains"       = { kind = "allow", values = [var.customer_id] }
    "iam.disableServiceAccountKeyCreation" = { kind = "boolean", values = [] }
    "compute.vmExternalIpAccess"           = { kind = "deny_all", values = [] }
    "storage.uniformBucketLevelAccess"     = { kind = "boolean", values = [] }
    "compute.requireOsLogin"               = { kind = "boolean", values = [] }
    "sql.restrictPublicIp"                 = { kind = "boolean", values = [] }
  }
}

resource "google_org_policy_policy" "this" {
  for_each = var.org_policies_enabled ? local.org_policies : {}

  name   = "${local.org}/policies/${each.key}"
  parent = local.org

  dynamic "spec" {
    for_each = contains(var.dry_run_constraints, each.key) ? [] : [1]
    content {
      rules {
        enforce  = each.value.kind == "boolean" ? "TRUE" : null
        deny_all = each.value.kind == "deny_all" ? "TRUE" : null

        dynamic "values" {
          for_each = each.value.kind == "allow" ? [1] : []
          content {
            allowed_values = each.value.values
          }
        }
      }
    }
  }

  dynamic "dry_run_spec" {
    for_each = contains(var.dry_run_constraints, each.key) ? [1] : []
    content {
      rules {
        enforce  = each.value.kind == "boolean" ? "TRUE" : null
        deny_all = each.value.kind == "deny_all" ? "TRUE" : null

        dynamic "values" {
          for_each = each.value.kind == "allow" ? [1] : []
          content {
            allowed_values = each.value.values
          }
        }
      }
    }
  }
}
