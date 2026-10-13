package golden.finops.tagging_test

import rego.v1

import data.golden.finops.tagging

plan(changes) := {"resource_changes": changes}

create(type, address, after) := {"address": address, "mode": "managed", "type": type, "change": {"actions": ["create"], "after": after, "after_unknown": {}}}

full_tags := {"Project": "golden", "Environment": "dev", "Team": "payments", "CostCenter": "cc-1001", "Owner": "payments@example.com"}

gcp_labels := {"project": "golden", "environment": "dev", "team": "payments", "cost_center": "cc-1001", "owner": "payments"}

test_fully_tagged_aws_resource_allowed if {
	bucket := create("aws_s3_bucket", "aws_s3_bucket.data", {"bucket": "x", "tags": {}, "tags_all": full_tags})
	tagging.allow with input as plan([bucket])
}

test_missing_tags_denied_and_listed if {
	bucket := create("aws_s3_bucket", "aws_s3_bucket.data", {"bucket": "x", "tags": {"Project": "golden"}, "tags_all": {"Project": "golden"}})
	some msg in tagging.deny with input as plan([bucket])
	contains(msg, "aws_s3_bucket.data")
	contains(msg, "CostCenter")
	contains(msg, "Team")
	not contains(msg, "\"Project\"")
}

test_tags_all_carries_provider_default_tags if {
	# Resource sets only Team; tags_all has the provider default_tags merged in.
	vm := create("aws_instance", "aws_instance.app", {"tags": {"Team": "payments"}, "tags_all": full_tags})
	tagging.allow with input as plan([vm])
}

test_literal_default_tags_cover_unknown_tags_all if {
	vm := {
		"address": "aws_instance.app", "mode": "managed", "type": "aws_instance",
		"change": {"actions": ["create"], "after": {"tags": {"Team": "payments", "Owner": "a"}}, "after_unknown": {"tags_all": true}},
	}
	input_doc := {
		"resource_changes": [vm],
		"configuration": {"provider_config": {"aws": {"name": "aws", "expressions": {"default_tags": [{"tags": {"constant_value": {"Project": "golden", "Environment": "dev", "CostCenter": "cc-1"}}}]}}}},
	}
	tagging.allow with input as input_doc
}

test_unknown_tag_value_counts_as_present if {
	vm := {
		"address": "aws_instance.app", "mode": "managed", "type": "aws_instance",
		"change": {
			"actions": ["create"],
			"after": {"tags": {}, "tags_all": json.remove(full_tags, ["Owner"])},
			"after_unknown": {"tags_all": {"Owner": true}},
		},
	}
	tagging.allow with input as plan([vm])
}

test_empty_tag_value_is_missing if {
	tags := json.patch(full_tags, [{"op": "replace", "path": "/Owner", "value": " "}])
	bucket := create("aws_s3_bucket", "aws_s3_bucket.data", {"tags_all": tags})
	some msg in tagging.deny with input as plan([bucket])
	contains(msg, "Owner")
}

test_azure_tags_checked if {
	rg := create("azurerm_resource_group", "azurerm_resource_group.app", {"name": "rg", "tags": {"Project": "golden"}})
	count(tagging.deny) == 1 with input as plan([rg])
	tagging.allow with input as plan([create("azurerm_resource_group", "azurerm_resource_group.app", {"tags": full_tags})])
}

test_gcp_snake_case_labels_satisfy_required_tags if {
	bucket := create("google_storage_bucket", "google_storage_bucket.data", {"labels": gcp_labels, "effective_labels": gcp_labels})
	tagging.allow with input as plan([bucket])
}

test_gcp_effective_labels_include_default_labels if {
	bucket := create("google_storage_bucket", "google_storage_bucket.data", {"labels": {"team": "payments"}, "effective_labels": gcp_labels})
	tagging.allow with input as plan([bucket])
}

test_gcp_missing_labels_say_labels if {
	cluster := create("google_container_cluster", "google_container_cluster.gke", {"resource_labels": {"team": "x"}})
	some msg in tagging.deny with input as plan([cluster])
	contains(msg, "labels")
}

test_untaggable_types_ignored if {
	att := create("aws_iam_role_policy_attachment", "aws_iam_role_policy_attachment.x", {"policy_arn": "arn"})
	tagging.allow with input as plan([att])
}

test_deletes_and_data_sources_ignored if {
	del := {"address": "aws_s3_bucket.old", "mode": "managed", "type": "aws_s3_bucket", "change": {"actions": ["delete"], "after": null}}
	ds := {"address": "data.aws_vpc.x", "mode": "data", "type": "aws_vpc", "change": {"actions": ["read"], "after": {}}}
	tagging.allow with input as plan([del, ds])
}

test_required_set_overridable if {
	bucket := create("aws_s3_bucket", "aws_s3_bucket.data", {"tags_all": {"Team": "payments"}})
	tagging.allow with input as plan([bucket]) with data.finops.required_tags as ["Team"]
}

test_exempt_address_skipped if {
	bucket := create("aws_s3_bucket", "aws_s3_bucket.legacy", {"tags_all": {}})
	tagging.allow with input as plan([bucket]) with data.finops.exempt_addresses as ["aws_s3_bucket.legacy"]
}

test_unknown_environment_warns if {
	tags := json.patch(full_tags, [{"op": "replace", "path": "/Environment", "value": "qa-temp"}])
	bucket := create("aws_s3_bucket", "aws_s3_bucket.data", {"tags_all": tags})
	count(tagging.warn) == 1 with input as plan([bucket])
	tagging.allow with input as plan([bucket])
}

test_coverage_counts if {
	good := create("aws_s3_bucket", "aws_s3_bucket.a", {"tags_all": full_tags})
	bad := create("aws_s3_bucket", "aws_s3_bucket.b", {"tags_all": {}})
	tagging.coverage == {"taggable": 2, "compliant": 1} with input as plan([good, bad])
}
