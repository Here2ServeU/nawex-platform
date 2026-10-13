package golden.network_test

import rego.v1

import data.golden.network

plan(changes) := {"resource_changes": changes}

create(type, address, after) := {
	"address": address,
	"type": type,
	"name": split(address, ".")[count(split(address, ".")) - 1],
	"change": {"actions": ["create"], "after": after, "after_unknown": {}},
}

sg_rule(cidr, from, to, protocol) := create("aws_security_group_rule", "aws_security_group_rule.r", {
	"type": "ingress",
	"cidr_blocks": [cidr],
	"ipv6_cidr_blocks": null,
	"from_port": from,
	"to_port": to,
	"protocol": protocol,
})

# ----------------------------------------------------------------------------- AWS security groups
test_https_from_internet_allowed if {
	network.allow with input as plan([sg_rule("0.0.0.0/0", 443, 443, "tcp")])
}

test_ssh_from_internet_denied if {
	some msg in network.deny with input as plan([sg_rule("0.0.0.0/0", 22, 22, "tcp")])
	contains(msg, "admin port 22")
}

test_ssh_from_corporate_range_allowed if {
	network.allow with input as plan([sg_rule("10.0.0.0/8", 22, 22, "tcp")])
}

test_port_range_covering_rdp_denied if {
	some msg in network.deny with input as plan([sg_rule("0.0.0.0/0", 3000, 4000, "tcp")])
	contains(msg, "admin port 3389")
}

test_all_protocols_from_internet_denied if {
	some msg in network.deny with input as plan([sg_rule("0.0.0.0/0", 0, 0, "-1")])
	contains(msg, "all ports")
}

test_icmp_from_internet_allowed if {
	network.allow with input as plan([sg_rule("0.0.0.0/0", -1, -1, "icmp")])
}

test_inline_ipv6_ingress_denied if {
	sg := create("aws_security_group", "aws_security_group.web", {"ingress": [{
		"cidr_blocks": [],
		"ipv6_cidr_blocks": ["::/0"],
		"from_port": 22,
		"to_port": 22,
		"protocol": "tcp",
	}]})
	count(network.deny) == 1 with input as plan([sg])
}

test_vpc_ingress_rule_all_traffic_denied if {
	rule := create("aws_vpc_security_group_ingress_rule", "aws_vpc_security_group_ingress_rule.any", {
		"cidr_ipv4": "0.0.0.0/0",
		"cidr_ipv6": null,
		"ip_protocol": "-1",
		"from_port": null,
		"to_port": null,
	})
	count(network.deny) == 1 with input as plan([rule])
}

# ----------------------------------------------------------------------------- Azure NSG / GCP firewall
nsg_rule(source, port) := create("azurerm_network_security_rule", "azurerm_network_security_rule.r", {
	"direction": "Inbound",
	"access": "Allow",
	"protocol": "Tcp",
	"source_address_prefix": source,
	"source_address_prefixes": null,
	"destination_port_range": port,
	"destination_port_ranges": null,
})

test_nsg_rdp_from_internet_tag_denied if {
	some msg in network.deny with input as plan([nsg_rule("Internet", "3389")])
	contains(msg, "admin port 3389")
}

test_nsg_wildcard_ports_denied if {
	some msg in network.deny with input as plan([nsg_rule("*", "*")])
	contains(msg, "all ports")
}

test_nsg_from_vnet_allowed if {
	network.allow with input as plan([nsg_rule("VirtualNetwork", "22")])
}

test_nsg_deny_rule_ignored if {
	r := json.patch(nsg_rule("*", "*"), [{"op": "replace", "path": "/change/after/access", "value": "Deny"}])
	network.allow with input as plan([r])
}

test_inline_nsg_rule_denied if {
	nsg := create("azurerm_network_security_group", "azurerm_network_security_group.app", {"security_rule": [{
		"direction": "Inbound",
		"access": "Allow",
		"protocol": "*",
		"source_address_prefix": "0.0.0.0/0",
		"destination_port_range": "20-25",
	}]})
	count(network.deny) == 1 with input as plan([nsg])
}

gcp_fw(sources, allow) := create("google_compute_firewall", "google_compute_firewall.fw", {
	"direction": "INGRESS",
	"source_ranges": sources,
	"allow": allow,
})

test_gcp_ssh_from_world_denied if {
	count(network.deny) == 1 with input as plan([gcp_fw(["0.0.0.0/0"], [{"protocol": "tcp", "ports": ["22"]}])])
}

test_gcp_iap_ssh_allowed if {
	network.allow with input as plan([gcp_fw(["35.235.240.0/20"], [{"protocol": "tcp", "ports": ["22"]}])])
}

test_gcp_tcp_without_ports_means_all_ports if {
	some msg in network.deny with input as plan([gcp_fw(["0.0.0.0/0"], [{"protocol": "tcp", "ports": []}])])
	contains(msg, "all ports")
}

test_gcp_egress_ignored if {
	fw := json.patch(gcp_fw(["0.0.0.0/0"], [{"protocol": "all", "ports": []}]), [{"op": "replace", "path": "/change/after/direction", "value": "EGRESS"}])
	network.allow with input as plan([fw])
}

# ----------------------------------------------------------------------------- public data tier
test_public_ip_on_data_subnet_denied if {
	subnet := create("aws_subnet", "aws_subnet.data", {"map_public_ip_on_launch": true, "tags": {"Name": "golden-prod-data-a"}})
	count(network.deny) == 1 with input as plan([subnet])
}

test_public_ip_on_public_subnet_allowed if {
	subnet := create("aws_subnet", "aws_subnet.public", {"map_public_ip_on_launch": true, "tags": {"Name": "golden-prod-public-a", "Tier": "public"}})
	network.allow with input as plan([subnet])
}

test_public_rds_denied if {
	db := create("aws_db_instance", "aws_db_instance.main", {"publicly_accessible": true})
	count(network.deny) == 1 with input as plan([db])
}

test_s3_public_access_block_disabled_denied if {
	pab := create("aws_s3_bucket_public_access_block", "aws_s3_bucket_public_access_block.b", {
		"block_public_acls": true,
		"block_public_policy": false,
		"ignore_public_acls": true,
		"restrict_public_buckets": true,
	})
	some msg in network.deny with input as plan([pab])
	contains(msg, "block_public_policy")
}

test_cloud_sql_open_to_world_denied if {
	sql := create("google_sql_database_instance", "google_sql_database_instance.db", {"settings": [{"ip_configuration": [{"authorized_networks": [{"value": "0.0.0.0/0"}]}]}]})
	count(network.deny) == 1 with input as plan([sql])
}

# ----------------------------------------------------------------------------- flow logs (warn)
vpc := create("aws_vpc", "aws_vpc.main", {"cidr_block": "10.0.0.0/16"})

test_vpc_without_flow_log_warns if {
	count(network.warn) == 1 with input as plan([vpc])
	network.allow with input as plan([vpc])
}

test_vpc_with_flow_log_reference_ok if {
	fl := create("aws_flow_log", "aws_flow_log.main", {"traffic_type": "ALL"})
	cfg := {"root_module": {"resources": [{
		"address": "aws_flow_log.main",
		"type": "aws_flow_log",
		"name": "main",
		"expressions": {"vpc_id": {"references": ["aws_vpc.main.id", "aws_vpc.main"]}},
	}]}}
	count(network.warn) == 0 with input as {"resource_changes": [vpc, fl], "configuration": cfg}
}

test_vpc_in_module_with_unknown_flow_log_ok if {
	mvpc := object.union(vpc, {"address": "module.vpc.aws_vpc.this[0]", "module_address": "module.vpc"})
	fl := object.union(create("aws_flow_log", "module.vpc.aws_flow_log.this[0]", {}), {
		"module_address": "module.vpc",
		"change": {"actions": ["create"], "after": {}, "after_unknown": {"vpc_id": true}},
	})
	count(network.warn) == 0 with input as plan([mvpc, fl])
}

test_gcp_subnet_without_flow_logs_warns if {
	subnet := create("google_compute_subnetwork", "google_compute_subnetwork.s", {"log_config": []})
	count(network.warn) == 1 with input as plan([subnet])
}

# ----------------------------------------------------------------------------- WAF on internet-facing ALBs (warn)
alb := create("aws_lb", "aws_lb.web", {"internal": false, "load_balancer_type": "application"})

test_public_alb_without_waf_warns if {
	some msg in network.warn with input as plan([alb])
	contains(msg, "aws_wafv2_web_acl_association")
}

test_public_alb_with_waf_ok if {
	assoc := create("aws_wafv2_web_acl_association", "module.edge.aws_wafv2_web_acl_association.web", {})
	cfg := {"root_module": {"resources": [{
		"type": "aws_wafv2_web_acl_association",
		"name": "web",
		"expressions": {"resource_arn": {"references": ["aws_lb.web.arn", "aws_lb.web"]}},
	}]}}
	count(network.warn) == 0 with input as {"resource_changes": [alb, assoc], "configuration": cfg}
}

test_waf_reference_in_other_module_does_not_count if {
	cfg := {"root_module": {"module_calls": {"edge": {"module": {"resources": [{
		"type": "aws_wafv2_web_acl_association",
		"name": "web",
		"expressions": {"resource_arn": {"references": ["aws_lb.web.arn"]}},
	}]}}}}}
	count(network.warn) == 1 with input as {"resource_changes": [alb], "configuration": cfg}
}

test_internal_alb_and_nlb_need_no_waf if {
	internal := create("aws_lb", "aws_lb.internal", {"internal": true, "load_balancer_type": "application"})
	nlb := create("aws_lb", "aws_lb.nlb", {"internal": false, "load_balancer_type": "network"})
	count(network.warn) == 0 with input as plan([internal, nlb])
}
