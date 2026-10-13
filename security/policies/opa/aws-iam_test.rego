package golden.aws.iam_test

import rego.v1

import data.golden.aws.iam

plan(changes) := {"resource_changes": changes}

create(type, address, after) := {"address": address, "type": type, "change": {"actions": ["create"], "after": after, "after_unknown": {}}}

irsa_trust := json.marshal({"Version": "2012-10-17", "Statement": [{
	"Effect": "Allow",
	"Action": "sts:AssumeRoleWithWebIdentity",
	"Principal": {"Federated": "arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/X"},
}]})

good_role := create("aws_iam_role", "aws_iam_role.workload", {
	"name": "golden-dev-workload",
	"assume_role_policy": irsa_trust,
	"permissions_boundary": "arn:aws:iam::123456789012:policy/golden-workload-boundary",
})

test_bounded_role_allowed if {
	iam.allow with input as plan([good_role])
}

test_role_without_boundary_denied if {
	role := json.remove(good_role, ["change/after/permissions_boundary"])
	count(iam.deny) == 1 with input as plan([role])
}

test_boundary_known_after_apply_allowed if {
	role := json.patch(good_role, [
		{"op": "remove", "path": "/change/after/permissions_boundary"},
		{"op": "add", "path": "/change/after_unknown/permissions_boundary", "value": true},
	])
	iam.allow with input as plan([role])
}

test_iam_users_and_keys_denied if {
	changes := [
		create("aws_iam_user", "aws_iam_user.svc", {"name": "svc"}),
		create("aws_iam_access_key", "aws_iam_access_key.svc", {"user": "svc"}),
	]
	count(iam.deny) == 2 with input as plan(changes)
}

test_wildcard_admin_policy_denied if {
	policy := create("aws_iam_policy", "aws_iam_policy.admin", {
		"name": "admin",
		"policy": json.marshal({"Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]}),
		"tags": {},
	})
	some msg in iam.deny with input as plan([policy])
	contains(msg, "full admin")
}

test_boundary_policy_exempt_from_wildcard_rule if {
	boundary := create("aws_iam_policy", "module.permission_boundary.aws_iam_policy.boundary", {
		"name": "golden-workload-boundary",
		"policy": json.marshal({"Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]}),
		"tags": {"golden:policy-type": "permissions-boundary"},
	})
	iam.allow with input as plan([boundary])
}

test_not_action_denied if {
	inline := create("aws_ssoadmin_permission_set_inline_policy", "x", {"inline_policy": json.marshal({"Statement": [{"Effect": "Allow", "NotAction": "iam:*", "Resource": "*"}]})})
	count(iam.deny) == 1 with input as plan([inline])
}

test_admin_attachment_to_role_denied if {
	att := create("aws_iam_role_policy_attachment", "aws_iam_role_policy_attachment.x", {"policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess"})
	count(iam.deny) == 1 with input as plan([att])
}

test_open_trust_denied if {
	role := json.patch(good_role, [{"op": "replace", "path": "/change/after/assume_role_policy", "value": json.marshal({"Statement": {"Effect": "Allow", "Action": "sts:AssumeRole", "Principal": {"AWS": "*"}}})}])
	some msg in iam.deny with input as plan([role])
	contains(msg, "any AWS principal")
}

test_cross_account_without_external_id_warns if {
	trust := {"Statement": [{"Effect": "Allow", "Action": "sts:AssumeRole", "Principal": {"AWS": "arn:aws:iam::999999999999:root"}}]}
	role := json.patch(good_role, [{"op": "replace", "path": "/change/after/assume_role_policy", "value": json.marshal(trust)}])
	iam.allow with input as plan([role])
	count(iam.warn) == 1 with input as plan([role])
}

test_cross_account_with_external_id_quiet if {
	trust := {"Statement": [{
		"Effect": "Allow", "Action": "sts:AssumeRole",
		"Principal": {"AWS": ["arn:aws:iam::999999999999:role/wiz"]},
		"Condition": {"StringEquals": {"sts:ExternalId": "tenant-external-id"}},
	}]}
	role := json.patch(good_role, [{"op": "replace", "path": "/change/after/assume_role_policy", "value": json.marshal(trust)}])
	count(iam.warn) == 0 with input as plan([role])
}

test_session_duration_limits if {
	long := create("aws_ssoadmin_permission_set", "a", {"name": "Developer", "session_duration": "PT12H"})
	ok := create("aws_ssoadmin_permission_set", "b", {"name": "Developer", "session_duration": "PT7H30M"})
	privileged := create("aws_ssoadmin_permission_set", "c", {"name": "BreakGlassAdmin", "session_duration": "PT2H"})
	count(iam.deny) == 1 with input as plan([long])
	iam.allow with input as plan([ok])
	count(iam.deny) == 1 with input as plan([privileged])
}

test_admin_only_on_break_glass if {
	att := object.union(create("aws_ssoadmin_managed_policy_attachment", "x", {"managed_policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess"}), {"index": "Developer|AdministratorAccess"})
	bg := object.union(att, {"index": "BreakGlassAdmin|AdministratorAccess"})
	count(iam.deny) == 1 with input as plan([att])
	iam.allow with input as plan([bg])
}

test_oversized_scp_denied if {
	scp := create("aws_organizations_policy", "s", {"type": "SERVICE_CONTROL_POLICY", "content": concat("", array.concat(["{"], [x | some _ in numbers.range(1, 5200); x := " "]))})
	count(iam.deny) == 1 with input as plan([scp])
}

test_guardrail_removal_warns if {
	rc := {"address": "a", "type": "aws_organizations_policy_attachment", "change": {"actions": ["delete"], "after": null}}
	count(iam.warn) == 1 with input as plan([rc])
}
