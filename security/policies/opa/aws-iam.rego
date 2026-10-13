# AWS IAM guardrails for Terraform plans: the pipeline layer of the control-placement model
# (docs/modernization/aws-iam-modernization.md). It catches at review time what the SCPs/RCPs
# would otherwise only block at apply time, and things no SCP can express.
#
#   terraform plan -out tf.plan && terraform show -json tf.plan > plan.json
#   opa eval -d security/policies/opa -i plan.json 'data.golden.aws.iam.deny'
#   (or: scripts/iam-policy-gate.sh <terraform dir>)
package golden.aws.iam

import rego.v1

# Keep in sync with security/identity/access-model.yaml.
boundary_policy_name := "golden-workload-boundary"

max_session_hours := 8

max_privileged_session_hours := 1

privileged_permission_sets := {"BreakGlassAdmin"}

privileged_managed_policies := {"AdministratorAccess", "IAMFullAccess"}

scp_max_chars := 5120

default allow := false

allow if count(deny) == 0

# Resources being created or updated, with their planned state.
changes contains rc if {
	some rc in input.resource_changes
	some action in rc.change.actions
	action in {"create", "update"}
}

deletions contains rc if {
	some rc in input.resource_changes
	"delete" in rc.change.actions
}

as_list(x) := x if is_array(x)

as_list(x) := [x] if not is_array(x)

doc(raw) := json.unmarshal(raw) if is_string(raw)

doc(raw) := raw if is_object(raw)

statements(raw) := as_list(doc(raw).Statement)

# ----------------------------------------------------------------------------- permission boundaries
boundary_ok(rc) if endswith(rc.change.after.permissions_boundary, sprintf("/%s", [boundary_policy_name]))

# The boundary ARN is often created in the same plan and only known at apply time.
boundary_ok(rc) if rc.change.after_unknown.permissions_boundary == true

deny contains msg if {
	some rc in changes
	rc.type == "aws_iam_role"
	not boundary_ok(rc)
	msg := sprintf("%s: IAM roles must set permissions_boundary to the %s policy", [rc.address, boundary_policy_name])
}

# ----------------------------------------------------------------------------- no long-lived IAM users
iam_user_types := {"aws_iam_user", "aws_iam_access_key", "aws_iam_user_login_profile"}

deny contains msg if {
	some rc in changes
	rc.type in iam_user_types
	msg := sprintf("%s: IAM users and access keys are not allowed; grant access through IAM Identity Center permission sets", [rc.address])
}

# ----------------------------------------------------------------------------- no wildcard admin
policy_documents contains [rc.address, raw] if {
	some rc in changes
	rc.type in {"aws_iam_policy", "aws_iam_role_policy"}
	not rc.change.after.tags["golden:policy-type"] == "permissions-boundary"
	raw := rc.change.after.policy
}

policy_documents contains [rc.address, raw] if {
	some rc in changes
	rc.type == "aws_ssoadmin_permission_set_inline_policy"
	raw := rc.change.after.inline_policy
}

is_wildcard(x) if x == "*"

is_wildcard(x) if "*" in x

deny contains msg if {
	some [address, raw] in policy_documents
	some s in statements(raw)
	s.Effect == "Allow"
	is_wildcard(s.Action)
	is_wildcard(s.Resource)
	msg := sprintf("%s: Allow Action \"*\" on Resource \"*\" (full admin) is not allowed; use the BreakGlassAdmin permission set", [address])
}

deny contains msg if {
	some [address, raw] in policy_documents
	some s in statements(raw)
	s.Effect == "Allow"
	s.NotAction
	msg := sprintf("%s: Allow with NotAction grants everything not listed; enumerate actions instead", [address])
}

deny contains msg if {
	some rc in changes
	rc.type in {"aws_iam_role_policy_attachment", "aws_iam_group_policy_attachment"}
	some name in privileged_managed_policies
	endswith(rc.change.after.policy_arn, sprintf(":policy/%s", [name]))
	msg := sprintf("%s: %s must not be attached to IAM roles or groups; use the break-glass permission set", [rc.address, name])
}

# ----------------------------------------------------------------------------- trust policies
principal_values(s) := as_list(s.Principal.AWS) if s.Principal.AWS

principal_values(s) := ["*"] if s.Principal == "*"

deny contains msg if {
	some rc in changes
	rc.type == "aws_iam_role"
	some s in statements(rc.change.after.assume_role_policy)
	s.Effect == "Allow"
	"*" in principal_values(s)
	not s.Condition
	msg := sprintf("%s: trust policy allows any AWS principal (\"*\") with no condition", [rc.address])
}

guarded_cross_account(s) if s.Condition.StringEquals["sts:ExternalId"]

guarded_cross_account(s) if s.Condition.StringEquals["aws:PrincipalOrgID"]

guarded_cross_account(s) if s.Condition.StringLike["aws:PrincipalOrgID"]

warn contains msg if {
	some rc in changes
	rc.type == "aws_iam_role"
	some s in statements(rc.change.after.assume_role_policy)
	s.Effect == "Allow"
	some p in principal_values(s)
	p != "*"
	not guarded_cross_account(s)
	msg := sprintf("%s: cross-account trust for %s has no sts:ExternalId or aws:PrincipalOrgID condition", [rc.address, p])
}

# ----------------------------------------------------------------------------- Identity Center
duration_hours(d) := num(h) + (num(m) / 60) if {
	[_, h, m] := regex.find_all_string_submatch_n(`^PT(?:(\d+)H)?(?:(\d+)M)?$`, d, 1)[0]
}

num("") := 0

num(s) := to_number(s) if s != ""

deny contains msg if {
	some rc in changes
	rc.type == "aws_ssoadmin_permission_set"
	duration_hours(rc.change.after.session_duration) > max_session_hours
	msg := sprintf("%s: session_duration %s exceeds %dh", [rc.address, rc.change.after.session_duration, max_session_hours])
}

deny contains msg if {
	some rc in changes
	rc.type == "aws_ssoadmin_permission_set"
	rc.change.after.name in privileged_permission_sets
	duration_hours(rc.change.after.session_duration) > max_privileged_session_hours
	msg := sprintf("%s: privileged permission set sessions are limited to %dh", [rc.address, max_privileged_session_hours])
}

# identity-center module keys managed policy attachments "<PermissionSet>|<policy path/name>".
deny contains msg if {
	some rc in changes
	rc.type == "aws_ssoadmin_managed_policy_attachment"
	permission_set := split(rc.index, "|")[0]
	not permission_set in privileged_permission_sets
	some name in privileged_managed_policies
	endswith(rc.change.after.managed_policy_arn, sprintf(":policy/%s", [name]))
	msg := sprintf("%s: %s may only be attached to %v", [rc.address, name, privileged_permission_sets])
}

# ----------------------------------------------------------------------------- Organizations
deny contains msg if {
	some rc in changes
	rc.type == "aws_organizations_policy"
	rc.change.after.type in {"SERVICE_CONTROL_POLICY", "RESOURCE_CONTROL_POLICY"}
	count(rc.change.after.content) > scp_max_chars
	msg := sprintf("%s: policy is %d characters; Organizations allows %d", [rc.address, count(rc.change.after.content), scp_max_chars])
}

warn contains msg if {
	some rc in deletions
	rc.type in {"aws_organizations_policy", "aws_organizations_policy_attachment"}
	msg := sprintf("%s: removes an organization guardrail; needs an approved change (ops/runbooks/identity/guardrail-rollout.md)", [rc.address])
}
