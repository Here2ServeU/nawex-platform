# ------------------------------------------------------------------------------
# AZURE GOVERNANCE MODULE — management groups, Azure Policy, Entra ID personas
# ------------------------------------------------------------------------------
# The Azure counterpart of modules/aws/org-guardrails + modules/aws/identity-center:
#
#   AWS                                   Azure (this module)
#   Organization root / OUs           ->  intermediate root MG / child MGs
#   SCPs per OU                       ->  Azure Policy assignments per MG (deny,
#                                         deployIfNotExists)
#   Identity Center permission sets   ->  built-in role assignments to Entra groups
#   permission set session_duration   ->  PIM eligibility + activation policy
#
# Hierarchy (keys are the scopes used in security/identity/azure-access-model.yaml):
#
#   root
#   ├── platform                 identity, connectivity, management subscriptions
#   ├── landing-zones
#   │   ├── landing-zones-prod
#   │   └── landing-zones-nonprod
#   ├── sandbox
#   └── decommissioned           cancelled subscriptions wait here
#
# Run with an identity holding Management Group Contributor + Resource Policy
# Contributor + User Access Administrator at the tenant root (or the parent MG).
# ------------------------------------------------------------------------------

locals {
  top_level = toset(["platform", "landing-zones", "sandbox", "decommissioned"])
  lz_level  = toset(["landing-zones-prod", "landing-zones-nonprod"])

  display_names = {
    "platform"              = "Platform"
    "landing-zones"         = "Landing Zones"
    "landing-zones-prod"    = "Production"
    "landing-zones-nonprod" = "Non-production"
    "sandbox"               = "Sandbox"
    "decommissioned"        = "Decommissioned"
  }

  mg_ids = merge(
    { "root" = azurerm_management_group.root.id },
    { for k, mg in azurerm_management_group.top : k => mg.id },
    { for k, mg in azurerm_management_group.landing_zones : k => mg.id },
  )
}

# ------------------------------------------------------------------ hierarchy
resource "azurerm_management_group" "root" {
  name                       = var.name_prefix
  display_name               = var.root_display_name
  parent_management_group_id = var.parent_management_group_id
}

resource "azurerm_management_group" "top" {
  for_each = local.top_level

  name                       = "${var.name_prefix}-${each.key}"
  display_name               = local.display_names[each.key]
  parent_management_group_id = azurerm_management_group.root.id

  # Subscriptions are placed with azurerm_management_group_subscription_association.
  lifecycle {
    ignore_changes = [subscription_ids]
  }
}

resource "azurerm_management_group" "landing_zones" {
  for_each = local.lz_level

  name                       = "${var.name_prefix}-${trimprefix(each.key, "landing-zones-")}"
  display_name               = local.display_names[each.key]
  parent_management_group_id = azurerm_management_group.top["landing-zones"].id

  lifecycle {
    ignore_changes = [subscription_ids]
  }
}

resource "azurerm_management_group_subscription_association" "this" {
  for_each = var.subscription_placement

  management_group_id = local.mg_ids[each.value]
  subscription_id     = "/subscriptions/${each.key}"
}

# ------------------------------------------------------------------ Azure Policy
# Built-in definitions by ID (stable across display-name changes). Verify with
#   az policy definition show --name <guid> --query "{name:displayName, effect:parameters.effect}"
locals {
  builtin = merge({
    allowed_locations  = "/providers/Microsoft.Authorization/policyDefinitions/e56962a6-4747-49cd-b67b-bf8b01975c4c" # Allowed locations
    require_tag        = "/providers/Microsoft.Authorization/policyDefinitions/871b6d14-10aa-478d-b590-94f262ecfa99" # Require a tag on resources
    nic_no_public_ip   = "/providers/Microsoft.Authorization/policyDefinitions/83a86a26-fd1f-447c-b59d-e51f44264114" # Network interfaces should not have public IPs
    storage_https      = "/providers/Microsoft.Authorization/policyDefinitions/404c3081-a854-4457-ae30-26a93ef643f9" # Secure transfer to storage accounts should be enabled
    not_allowed_types  = "/providers/Microsoft.Authorization/policyDefinitions/6c112d4e-5bc7-47ae-a041-ea2d9dccd749" # Not allowed resource types
    defender_for_cloud = "/providers/Microsoft.Authorization/policyDefinitions/ac076320-ddcf-4066-b451-6154267e8ad2" # Enable Microsoft Defender for Cloud on your subscription (DINE)
  }, var.policy_definition_ids)

  # Assignment names are limited to 24 characters at management-group scope.
  policy_assignments = merge(
    {
      "allowed-locations" = {
        scope       = "root"
        definition  = local.builtin.allowed_locations
        description = "Resources may only be created in approved regions."
        parameters  = { listOfAllowedLocations = { value = var.allowed_locations } }
        message     = "Region not allowed. Approved regions: ${join(", ", var.allowed_locations)}."
      }
      "deny-nic-public-ip" = {
        scope       = "landing-zones"
        definition  = local.builtin.nic_no_public_ip
        description = "Workloads reach the internet through the hub firewall / Front Door, never a NIC public IP."
        parameters  = {}
        message     = "Public IPs on network interfaces are denied in landing zones; publish through the platform ingress."
      }
      "storage-https-only" = {
        scope       = "root"
        definition  = local.builtin.storage_https
        description = "Storage accounts must require secure transfer (HTTPS / SMB 3 encryption)."
        parameters  = { effect = { value = "Deny" } }
        message     = "Storage accounts must set supportsHttpsTrafficOnly = true."
      }
      "deny-classic" = {
        scope       = "root"
        definition  = local.builtin.not_allowed_types
        description = "Classic (ASM) resources are retired and bypass Azure Resource Manager RBAC and policy."
        parameters  = { listOfResourceTypesNotAllowed = { value = var.classic_resource_types } }
        message     = "Classic (ASM) resource types are not allowed."
      }
    },
    {
      for tag in var.required_tags : substr("require-tag-${lower(tag)}", 0, 24) => {
        scope       = "root"
        definition  = local.builtin.require_tag
        description = "Every resource must carry the ${tag} tag (cost allocation and ownership)."
        parameters  = { tagName = { value = tag } }
        message     = "Missing required tag '${tag}'."
      }
    },
  )
}

resource "azurerm_management_group_policy_assignment" "this" {
  for_each = local.policy_assignments

  name                 = each.key
  display_name         = "${var.root_display_name}: ${each.key}"
  description          = each.value.description
  management_group_id  = local.mg_ids[lookup(var.policy_scope_overrides, each.key, each.value.scope)]
  policy_definition_id = each.value.definition
  parameters           = length(each.value.parameters) > 0 ? jsonencode(each.value.parameters) : null
  enforce              = var.enforce_policies

  non_compliance_message {
    content = each.value.message
  }
}

# deployIfNotExists needs a managed identity with rights to remediate.
resource "azurerm_management_group_policy_assignment" "defender" {
  count = var.defender_enabled ? 1 : 0

  name                 = "defender-for-cloud"
  display_name         = "${var.root_display_name}: Defender for Cloud on every subscription"
  description          = "Registers every subscription under the hierarchy with Microsoft Defender for Cloud."
  management_group_id  = local.mg_ids[lookup(var.policy_scope_overrides, "defender-for-cloud", "root")]
  policy_definition_id = local.builtin.defender_for_cloud
  location             = var.location
  enforce              = var.enforce_policies

  identity {
    type = "SystemAssigned"
  }

  non_compliance_message {
    content = "Microsoft Defender for Cloud must be enabled on this subscription."
  }
}

resource "azurerm_role_assignment" "defender_remediation" {
  count = var.defender_enabled ? 1 : 0

  scope                = azurerm_management_group_policy_assignment.defender[0].management_group_id
  role_definition_name = var.defender_remediation_role
  principal_id         = azurerm_management_group_policy_assignment.defender[0].identity[0].principal_id
  principal_type       = "ServicePrincipal"
}
