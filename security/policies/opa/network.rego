# Network guardrails for Terraform plans (AWS, Azure, GCP): the pipeline layer for the
# network controls in docs/networking/README.md. Catches at review time what the cloud
# would happily apply: admin ports open to the internet, public data tiers, missing
# flow logs, internet-facing load balancers with no WAF.
#
#   terraform plan -out tf.plan && terraform show -json tf.plan > plan.json
#   opa eval -d security/policies/opa -i plan.json 'data.golden.network.deny'
#   opa eval -d security/policies/opa -i plan.json 'data.golden.network.warn'
package golden.network

import rego.v1

admin_ports := {22, 3389}

# Sources that mean "anyone": IPv4/IPv6 any, and the Azure wildcard / service tags.
world_sources := {"0.0.0.0/0", "::/0", "*", "Internet", "internet", "Any", "any"}

data_tiers := {"data", "db", "database"}

icmp_protocols := {"icmp", "icmpv6", "1", "58"}

default allow := false

allow if count(deny) == 0

changes contains rc if {
	some rc in input.resource_changes
	some action in rc.change.actions
	action in {"create", "update"}
}

# Everything that will exist after apply (flow logs / WAF associations may already exist).
present contains rc if {
	some rc in input.resource_changes
	not "delete" in rc.change.actions
}

list(x) := x if is_array(x)

list(x) := [] if not is_array(x)

str_list(x) := [x] if is_string(x)

str_list(x) := [] if not is_string(x)

module_of(rc) := object.get(rc, "module_address", "")

# ----------------------------------------------------------------------------- port parsing
# "22" | "20-25" | "*"  ->  [from, to]
port_range("*") := [0, 65535]

port_range(s) := [to_number(p[0]), to_number(p[1])] if {
	contains(s, "-")
	p := split(s, "-")
}

port_range(s) := [to_number(s), to_number(s)] if {
	s != "*"
	not contains(s, "-")
}

all_ports(r) if r.protocol in {"-1", "all", "*"}

all_ports(r) if {
	r.from <= 0
	r.to >= 65535
}

# ----------------------------------------------------------------------------- normalized ingress rules
# Every cloud's ingress rule becomes {address, sources, protocol, from, to}.

# AWS: inline ingress blocks on aws_security_group.
ingress_rules contains {
	"address": rc.address,
	"sources": array.concat(list(object.get(i, "cidr_blocks", null)), list(object.get(i, "ipv6_cidr_blocks", null))),
	"protocol": lower(i.protocol),
	"from": i.from_port,
	"to": i.to_port,
} if {
	some rc in changes
	rc.type == "aws_security_group"
	some i in list(object.get(rc.change.after, "ingress", null))
}

# AWS: aws_security_group_rule (type = ingress).
ingress_rules contains {
	"address": rc.address,
	"sources": array.concat(list(object.get(a, "cidr_blocks", null)), list(object.get(a, "ipv6_cidr_blocks", null))),
	"protocol": lower(a.protocol),
	"from": a.from_port,
	"to": a.to_port,
} if {
	some rc in changes
	rc.type == "aws_security_group_rule"
	a := rc.change.after
	a.type == "ingress"
}

# AWS: aws_vpc_security_group_ingress_rule (ports are null for ip_protocol -1).
ingress_rules contains {
	"address": rc.address,
	"sources": array.concat(str_list(object.get(a, "cidr_ipv4", null)), str_list(object.get(a, "cidr_ipv6", null))),
	"protocol": lower(a.ip_protocol),
	"from": object.get(a, "from_port", 0),
	"to": object.get(a, "to_port", 65535),
} if {
	some rc in changes
	rc.type == "aws_vpc_security_group_ingress_rule"
	a := rc.change.after
}

# Azure: standalone NSG rules and inline security_rule blocks.
nsg_rules contains [rc.address, rc.change.after] if {
	some rc in changes
	rc.type == "azurerm_network_security_rule"
}

nsg_rules contains [rc.address, r] if {
	some rc in changes
	rc.type == "azurerm_network_security_group"
	some r in list(object.get(rc.change.after, "security_rule", null))
}

nsg_ports(r) := array.concat(str_list(object.get(r, "destination_port_range", null)), list(object.get(r, "destination_port_ranges", null)))

ingress_rules contains {
	"address": address,
	"sources": array.concat(str_list(object.get(r, "source_address_prefix", null)), list(object.get(r, "source_address_prefixes", null))),
	"protocol": lower(r.protocol),
	"from": pr[0],
	"to": pr[1],
} if {
	some [address, r] in nsg_rules
	r.direction == "Inbound"
	r.access == "Allow"
	some spec in nsg_ports(r)
	pr := port_range(spec)
}

# GCP: google_compute_firewall allow blocks (direction defaults to INGRESS).
gcp_ingress(a) if object.get(a, "direction", "INGRESS") == "INGRESS"

gcp_ingress(a) if a.direction == null

gcp_port_specs(allow) := ["*"] if count(list(object.get(allow, "ports", null))) == 0

gcp_port_specs(allow) := allow.ports if count(list(object.get(allow, "ports", null))) > 0

ingress_rules contains {
	"address": rc.address,
	"sources": list(object.get(a, "source_ranges", null)),
	"protocol": lower(allow.protocol),
	"from": pr[0],
	"to": pr[1],
} if {
	some rc in changes
	rc.type == "google_compute_firewall"
	a := rc.change.after
	gcp_ingress(a)
	some allow in list(object.get(a, "allow", null))
	some spec in gcp_port_specs(allow)
	pr := port_range(spec)
}

open_to_world(r) if {
	some s in r.sources
	s in world_sources
}

# ----------------------------------------------------------------------------- deny: internet exposure
deny contains msg if {
	some r in ingress_rules
	open_to_world(r)
	not r.protocol in icmp_protocols
	all_ports(r)
	msg := sprintf("%s: ingress allows all ports from the internet (%v)", [r.address, r.sources])
}

deny contains msg if {
	some r in ingress_rules
	open_to_world(r)
	not r.protocol in icmp_protocols
	not all_ports(r)
	some port in admin_ports
	r.from <= port
	port <= r.to
	msg := sprintf("%s: ingress allows admin port %d from the internet; use SSM Session Manager, Azure Bastion or IAP", [r.address, port])
}

# ----------------------------------------------------------------------------- deny: public data tier
tier_tag(tags) := lower(tags[k]) if {
	some k in {"Tier", "tier", "golden:tier"}
	tags[k]
}

data_subnet(rc) if tier_tag(object.get(rc.change.after, "tags", {})) in data_tiers

data_subnet(rc) if regex.match(`(?i)(^|[-_])(data|db|database)([-_]|$)`, object.get(object.get(rc.change.after, "tags", {}), "Name", ""))

deny contains msg if {
	some rc in changes
	rc.type == "aws_subnet"
	rc.change.after.map_public_ip_on_launch == true
	data_subnet(rc)
	msg := sprintf("%s: data-tier subnets must not auto-assign public IPs", [rc.address])
}

deny contains msg if {
	some rc in changes
	rc.type in {"aws_db_instance", "aws_rds_cluster_instance"}
	rc.change.after.publicly_accessible == true
	msg := sprintf("%s: databases must not be publicly accessible", [rc.address])
}

public_access_flags := ["block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"]

deny contains msg if {
	some rc in changes
	rc.type in {"aws_s3_bucket_public_access_block", "aws_s3_account_public_access_block"}
	some flag in public_access_flags
	rc.change.after[flag] == false
	msg := sprintf("%s: S3 public access block must set %s = true", [rc.address, flag])
}

deny contains msg if {
	some rc in changes
	rc.type == "google_sql_database_instance"
	some s in list(object.get(rc.change.after, "settings", null))
	some ip in list(object.get(s, "ip_configuration", null))
	some n in list(object.get(ip, "authorized_networks", null))
	n.value in world_sources
	msg := sprintf("%s: Cloud SQL authorized network %s exposes the database to the internet", [rc.address, n.value])
}

deny contains msg if {
	some rc in changes
	rc.type == "azurerm_mssql_server"
	rc.change.after.public_network_access_enabled == true
	msg := sprintf("%s: SQL server public network access must be disabled; use a Private Endpoint", [rc.address])
}

# ----------------------------------------------------------------------------- configuration references
# Flow logs and WAF associations usually reference resources created in the same plan,
# whose IDs are unknown until apply; the plan's configuration section has the references.
config_resources contains [module_addr, r] if {
	walk(input.configuration, [path, value])
	is_array(value.resources)
	names := [path[i + 1] | some i, p in path; p == "module_calls"]
	module_addr := concat(".", [sprintf("module.%s", [n]) | some n in names])
	some r in value.resources
}

references(module_addr, type, attr) := {ref |
	some [m, r] in config_resources
	m == module_addr
	r.type == type
	some ref in r.expressions[attr].references
}

references_resource(module_addr, type, attr, target) if {
	some ref in references(module_addr, type, attr)
	startswith(ref, sprintf("%s.%s", [target.type, target.name]))
}

# ----------------------------------------------------------------------------- warn: VPC flow logs
has_flow_log(vpc) if references_resource(module_of(vpc), "aws_flow_log", "vpc_id", vpc)

has_flow_log(vpc) if {
	some fl in present
	fl.type == "aws_flow_log"
	vpc.change.after.id
	fl.change.after.vpc_id == vpc.change.after.id
}

# Same module, flow log VPC known only after apply (e.g. terraform-aws-modules/vpc's local.vpc_id).
has_flow_log(vpc) if {
	some fl in present
	fl.type == "aws_flow_log"
	module_of(fl) == module_of(vpc)
	fl.change.after_unknown.vpc_id == true
}

warn contains msg if {
	some rc in changes
	rc.type == "aws_vpc"
	not has_flow_log(rc)
	msg := sprintf("%s: VPC has no aws_flow_log; flow logs are the network audit trail", [rc.address])
}

warn contains msg if {
	some rc in changes
	rc.type == "google_compute_subnetwork"
	count(list(object.get(rc.change.after, "log_config", null))) == 0
	msg := sprintf("%s: subnet has no log_config (VPC flow logs)", [rc.address])
}

# ----------------------------------------------------------------------------- warn: WAF on internet-facing ALBs
internet_facing_alb(rc) if {
	rc.type in {"aws_lb", "aws_alb"}
	rc.change.after.internal == false
	object.get(rc.change.after, "load_balancer_type", "application") in {"application", null}
}

has_waf(lb) if references_resource(module_of(lb), "aws_wafv2_web_acl_association", "resource_arn", lb)

has_waf(lb) if {
	some a in present
	a.type == "aws_wafv2_web_acl_association"
	lb.change.after.arn
	a.change.after.resource_arn == lb.change.after.arn
}

warn contains msg if {
	some rc in changes
	internet_facing_alb(rc)
	not has_waf(rc)
	msg := sprintf("%s: internet-facing ALB has no aws_wafv2_web_acl_association", [rc.address])
}
