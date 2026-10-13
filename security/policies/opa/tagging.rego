# FinOps tagging gate for Terraform plans: every taggable AWS, Azure and GCP resource
# must carry the cost allocation tags (labels on GCP) that showback/chargeback,
# budgets and anomaly monitors key on (docs/finops/README.md). This is the
# pipeline layer; AWS tag policies, Azure Policy and GCP org policy constraints
# are the runtime layers behind it.
#
#   terraform plan -out tf.plan && terraform show -json tf.plan > plan.json
#   opa eval -d security/policies/opa -i plan.json 'data.golden.finops.tagging.deny'
#
# Override the required set or exempt addresses with a data document:
#   {"finops": {"required_tags": ["Team", "CostCenter"], "exempt_addresses": ["aws_vpc.legacy"]}}
#
# Keys are compared case- and separator-insensitively, so "CostCenter" (AWS/Azure
# convention) is satisfied by "cost_center" or "cost-center" (GCP labels must be
# lowercase).
package golden.finops.tagging

import rego.v1

default required_tags := {"Project", "Environment", "Team", "CostCenter", "Owner"}

required_tags := {t | some t in data.finops.required_tags} if data.finops.required_tags

default exempt_addresses := set()

exempt_addresses := {a | some a in data.finops.exempt_addresses} if data.finops.exempt_addresses

allowed_environments := {"dev", "development", "test", "stage", "staging", "prod", "production", "sandbox", "shared"}

# ----------------------------------------------------------------------------- taggable types
aws_taggable := {
	"aws_instance", "aws_launch_template", "aws_ebs_volume", "aws_eip", "aws_nat_gateway",
	"aws_vpc", "aws_subnet", "aws_lb", "aws_s3_bucket", "aws_efs_file_system",
	"aws_db_instance", "aws_rds_cluster", "aws_dynamodb_table", "aws_elasticache_replication_group",
	"aws_redshift_cluster", "aws_opensearch_domain", "aws_msk_cluster", "aws_kinesis_stream",
	"aws_eks_cluster", "aws_eks_node_group", "aws_ecs_cluster", "aws_ecs_service", "aws_ecr_repository",
	"aws_lambda_function", "aws_sqs_queue", "aws_sns_topic", "aws_kms_key", "aws_secretsmanager_secret",
	"aws_cloudwatch_log_group", "aws_sagemaker_endpoint", "aws_sagemaker_notebook_instance",
	"aws_bedrock_provisioned_model_throughput", "aws_cloudfront_distribution", "aws_ec2_transit_gateway",
	"aws_vpc_endpoint", "aws_networkfirewall_firewall", "aws_fsx_lustre_file_system",
}

azure_taggable := {
	"azurerm_resource_group", "azurerm_kubernetes_cluster", "azurerm_kubernetes_cluster_node_pool",
	"azurerm_linux_virtual_machine", "azurerm_windows_virtual_machine", "azurerm_linux_virtual_machine_scale_set",
	"azurerm_managed_disk", "azurerm_virtual_network", "azurerm_public_ip", "azurerm_lb",
	"azurerm_application_gateway", "azurerm_firewall", "azurerm_nat_gateway", "azurerm_storage_account",
	"azurerm_postgresql_flexible_server", "azurerm_mssql_server", "azurerm_mssql_database",
	"azurerm_cosmosdb_account", "azurerm_redis_cache", "azurerm_key_vault", "azurerm_container_registry",
	"azurerm_log_analytics_workspace", "azurerm_service_plan", "azurerm_linux_web_app",
	"azurerm_linux_function_app", "azurerm_container_app", "azurerm_cognitive_account",
	"azurerm_machine_learning_workspace", "azurerm_eventhub_namespace", "azurerm_servicebus_namespace",
}

gcp_taggable := {
	"google_compute_instance", "google_compute_instance_template", "google_compute_disk",
	"google_compute_address", "google_compute_forwarding_rule", "google_container_cluster",
	"google_storage_bucket", "google_bigquery_dataset", "google_bigquery_table", "google_pubsub_topic",
	"google_pubsub_subscription", "google_cloud_run_v2_service", "google_cloudfunctions2_function",
	"google_redis_instance", "google_spanner_instance", "google_bigtable_instance", "google_dataproc_cluster",
	"google_artifact_registry_repository", "google_kms_crypto_key", "google_secret_manager_secret",
	"google_vertex_ai_endpoint", "google_filestore_instance", "google_alloydb_cluster",
}

taggable := (aws_taggable | azure_taggable) | gcp_taggable

# ----------------------------------------------------------------------------- planned resources
changes contains rc if {
	some rc in input.resource_changes
	not rc.mode == "data"
	rc.type in taggable
	some action in rc.change.actions
	action in {"create", "update"}
	not rc.address in exempt_addresses
}

# Tag maps that can hold the required keys, per provider. tags_all (AWS) and
# effective_labels (google >= 5) already include provider default_tags / default_labels.
tag_fields(type) := ["tags_all", "tags"] if startswith(type, "aws_")

tag_fields(type) := ["tags"] if startswith(type, "azurerm_")

tag_fields(type) := ["effective_labels", "terraform_labels", "labels", "resource_labels"] if startswith(type, "google_")

normalize(key) := lower(regex.replace(key, `[^A-Za-z0-9]`, ""))

# Keys with a non-empty value in the planned state.
known_keys(rc) := {normalize(k) |
	some field in tag_fields(rc.type)
	some k, v in object.get(rc.change.after, field, {})
	is_string(v)
	trim_space(v) != ""
}

# Keys whose value is only known after apply still count as present.
unknown_keys(rc) := {normalize(k) |
	some field in tag_fields(rc.type)
	unknowns := object.get(rc.change, ["after_unknown", field], {})
	is_object(unknowns)
	some k, u in unknowns
	u == true
}

# AWS provider default_tags written as literals in the configuration. Covers
# plans where tags_all is entirely unknown (e.g. a tag value from another resource).
provider_default_keys(rc) := {normalize(k) |
	startswith(rc.type, "aws_")
	some name, cfg in object.get(input, ["configuration", "provider_config"], {})
	object.get(cfg, "name", name) == "aws"
	some block in object.get(cfg, ["expressions", "default_tags"], [])
	some k, _ in object.get(block, ["tags", "constant_value"], {})
}

present_keys(rc) := (known_keys(rc) | unknown_keys(rc)) | provider_default_keys(rc)

missing(rc) := {t | some t in required_tags; not normalize(t) in present_keys(rc)}

label_word(type) := "labels" if startswith(type, "google_")

label_word(type) := "tags" if not startswith(type, "google_")

deny contains msg if {
	some rc in changes
	m := missing(rc)
	count(m) > 0
	msg := sprintf("%s: missing required cost allocation %s %v (docs/finops/README.md)", [rc.address, label_word(rc.type), sort(m)])
}

# ----------------------------------------------------------------------------- value hygiene
warn contains msg if {
	some rc in changes
	some field in tag_fields(rc.type)
	some k, v in object.get(rc.change.after, field, {})
	normalize(k) == "environment"
	is_string(v)
	not lower(v) in allowed_environments
	msg := sprintf("%s: Environment %q is not one of %v; showback groups by this value", [rc.address, v, sort(allowed_environments)])
}

default allow := false

allow if count(deny) == 0

# Tag coverage of the plan, for dashboards and PR comments.
coverage := {
	"taggable": count(changes),
	"compliant": count([rc | some rc in changes; count(missing(rc)) == 0]),
}
