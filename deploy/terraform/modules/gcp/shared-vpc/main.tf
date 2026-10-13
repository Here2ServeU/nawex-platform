# ------------------------------------------------------------------------------
# GCP SHARED VPC MODULE (host network, NAT, firewall baseline, PSC, flow logs)
# ------------------------------------------------------------------------------
# One host project owns the network; service projects (one per team/env) attach
# to it and deploy into its subnets. The GCP analogue of the AWS hub: a GCP VPC is
# global, so one network spans regions and subnets are regional.
#
#   network          custom-mode, GLOBAL dynamic routing (Cloud Router learns and
#                    advertises routes for every region, e.g. over Interconnect)
#   subnets          per region, Private Google Access on, VPC flow logs on,
#                    named secondary ranges for GKE pods and services (VPC-native)
#   Cloud Router+NAT one per subnet region, egress for private nodes, NAT logs
#   firewall         deny-all ingress (priority 65534, logged), allow IAP TCP
#                    forwarding 35.235.240.0/20 -> 22, allow internal from the
#                    subnets' primary + secondary ranges
#   PSC              Private Service Connect endpoint for Google APIs (all-apis or
#                    vpc-sc bundle) + private googleapis.com zone, so API traffic
#                    stays on an internal IP
#   service projects shared VPC attachments + per-subnet compute.networkUser
#
# Segmentation between prod and nonprod on GCP is usually separate host projects
# (one shared VPC per environment); see docs/networking/README.md.
# ------------------------------------------------------------------------------

locals {
  regions = toset([for s in values(var.subnets) : s.region])

  internal_ranges = distinct(concat(
    [for s in values(var.subnets) : s.ip_cidr_range],
    flatten([for s in values(var.subnets) : values(s.secondary_ranges)]),
  ))

  subnet_iam = merge([
    for subnet, members in var.subnet_users : {
      for m in members : "${subnet}|${m}" => { subnet = subnet, member = m }
    }
  ]...)
}

resource "google_compute_shared_vpc_host_project" "host" {
  project = var.host_project_id
}

resource "google_compute_network" "this" {
  project                 = var.host_project_id
  name                    = var.name
  auto_create_subnetworks = false
  routing_mode            = "GLOBAL"
  mtu                     = var.mtu
}

resource "google_compute_subnetwork" "this" {
  for_each = var.subnets

  project                  = var.host_project_id
  name                     = each.key
  region                   = each.value.region
  network                  = google_compute_network.this.id
  ip_cidr_range            = each.value.ip_cidr_range
  private_ip_google_access = true
  stack_type               = var.enable_ipv6 ? "IPV4_IPV6" : "IPV4_ONLY"
  ipv6_access_type         = var.enable_ipv6 ? "INTERNAL" : null

  dynamic "secondary_ip_range" {
    for_each = each.value.secondary_ranges
    content {
      range_name    = secondary_ip_range.key
      ip_cidr_range = secondary_ip_range.value
    }
  }

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = var.flow_log_sampling
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# ----------------------------------------------------------------------------- Cloud Router + Cloud NAT
resource "google_compute_router" "this" {
  for_each = local.regions

  project = var.host_project_id
  name    = "${var.name}-${each.key}"
  region  = each.key
  network = google_compute_network.this.id

  bgp {
    asn = var.router_asn
  }
}

resource "google_compute_router_nat" "this" {
  for_each = local.regions

  project                            = var.host_project_id
  name                               = "${var.name}-${each.key}-nat"
  router                             = google_compute_router.this[each.key].name
  region                             = each.key
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# ----------------------------------------------------------------------------- firewall baseline
resource "google_compute_firewall" "deny_all_ingress" {
  project     = var.host_project_id
  name        = "${var.name}-deny-all-ingress"
  network     = google_compute_network.this.id
  direction   = "INGRESS"
  priority    = 65534
  description = "Explicit, logged default deny (the implied deny is not logged)."

  deny {
    protocol = "all"
  }

  source_ranges = ["0.0.0.0/0"]

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_firewall" "deny_all_ingress_ipv6" {
  count = var.enable_ipv6 ? 1 : 0

  project   = var.host_project_id
  name      = "${var.name}-deny-all-ingress-v6"
  network   = google_compute_network.this.id
  direction = "INGRESS"
  priority  = 65534

  deny {
    protocol = "all"
  }

  source_ranges = ["::/0"]

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_firewall" "allow_iap_ssh" {
  project     = var.host_project_id
  name        = "${var.name}-allow-iap-ssh"
  network     = google_compute_network.this.id
  direction   = "INGRESS"
  priority    = 1000
  description = "SSH only through Identity-Aware Proxy TCP forwarding (no public SSH)."

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = var.iap_ssh_target_tags

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_firewall" "allow_internal" {
  project     = var.host_project_id
  name        = "${var.name}-allow-internal"
  network     = google_compute_network.this.id
  direction   = "INGRESS"
  priority    = 1000
  description = "East-west between the shared VPC's own primary and secondary (GKE) ranges."

  allow {
    protocol = "tcp"
  }
  allow {
    protocol = "udp"
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = local.internal_ranges
}

# ----------------------------------------------------------------------------- Private Service Connect (Google APIs)
resource "google_compute_global_address" "psc" {
  count = var.psc_enabled ? 1 : 0

  project      = var.host_project_id
  name         = "${var.name}-psc-googleapis"
  purpose      = "PRIVATE_SERVICE_CONNECT"
  address_type = "INTERNAL"
  address      = var.psc_address
  network      = google_compute_network.this.id
}

resource "google_compute_global_forwarding_rule" "psc" {
  count = var.psc_enabled ? 1 : 0

  project               = var.host_project_id
  name                  = var.psc_endpoint_name
  target                = var.psc_bundle
  network               = google_compute_network.this.id
  ip_address            = google_compute_global_address.psc[0].id
  load_balancing_scheme = ""
}

resource "google_dns_managed_zone" "googleapis" {
  count = var.psc_enabled ? 1 : 0

  project     = var.host_project_id
  name        = "${var.name}-googleapis"
  dns_name    = "googleapis.com."
  visibility  = "private"
  description = "googleapis.com -> Private Service Connect endpoint"

  private_visibility_config {
    networks {
      network_url = google_compute_network.this.id
    }
  }
}

resource "google_dns_record_set" "googleapis" {
  for_each = var.psc_enabled ? toset(["googleapis.com.", "*.googleapis.com."]) : toset([])

  project      = var.host_project_id
  managed_zone = google_dns_managed_zone.googleapis[0].name
  name         = each.value
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.psc[0].address]
}

# ----------------------------------------------------------------------------- service projects
resource "google_compute_shared_vpc_service_project" "this" {
  for_each = toset(var.service_project_ids)

  host_project    = google_compute_shared_vpc_host_project.host.project
  service_project = each.value
}

resource "google_compute_subnetwork_iam_member" "network_user" {
  for_each = local.subnet_iam

  project    = var.host_project_id
  region     = google_compute_subnetwork.this[each.value.subnet].region
  subnetwork = google_compute_subnetwork.this[each.value.subnet].name
  role       = "roles/compute.networkUser"
  member     = each.value.member
}
