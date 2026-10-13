variable "name" {
  description = "Identifier prefix for the replication instance/config, endpoints and task (lowercase, hyphens)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,40}$", var.name))
    error_message = "name must start with a letter and contain only lowercase letters, digits and hyphens (max 41)."
  }
}

variable "subnet_ids" {
  description = "Private subnets (at least two AZs) for the replication subnet group."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "Provide at least two subnets in different AZs."
  }
}

variable "security_group_ids" {
  description = "Security groups for the replication instance; must reach the source and target database ports."
  type        = list(string)
}

# ------------------------------------------------------------------------- compute
variable "serverless" {
  description = "Use DMS Serverless (aws_dms_replication_config) instead of a provisioned replication instance and task."
  type        = bool
  default     = false
}

variable "replication_instance_class" {
  description = "Provisioned replication instance class."
  type        = string
  default     = "dms.r6i.large"
}

variable "allocated_storage_gb" {
  description = "Replication instance storage (task logs and cached changes)."
  type        = number
  default     = 100
}

variable "engine_version" {
  description = "DMS engine version (null = AWS default)."
  type        = string
  default     = null
}

variable "multi_az" {
  description = "Multi-AZ replication instance / serverless compute."
  type        = bool
  default     = true
}

variable "serverless_min_capacity_units" {
  description = "Minimum DMS capacity units (DCU) for serverless."
  type        = number
  default     = 2
}

variable "serverless_max_capacity_units" {
  description = "Maximum DMS capacity units (DCU) for serverless."
  type        = number
  default     = 16
}

variable "preferred_maintenance_window" {
  type    = string
  default = "sun:04:00-sun:05:00"
}

# ------------------------------------------------------------------------- endpoints
variable "source_engine_name" {
  description = "DMS source engine (oracle, sqlserver, mysql, mariadb, postgres, db2, ...)."
  type        = string
}

variable "target_engine_name" {
  description = "DMS target engine (aurora-postgresql, aurora, postgres, oracle, sqlserver, mysql, ...)."
  type        = string
}

variable "source_database_name" {
  description = "Source database / service name (null when carried in the secret)."
  type        = string
  default     = null
}

variable "target_database_name" {
  description = "Target database name (null when carried in the secret)."
  type        = string
  default     = null
}

variable "source_secret_arn" {
  description = "Secrets Manager ARN with the source connection (username, password, host, port[, dbname])."
  type        = string
}

variable "target_secret_arn" {
  description = "Secrets Manager ARN with the target connection."
  type        = string
}

variable "secrets_kms_key_arns" {
  description = "KMS keys that encrypt the endpoint secrets (customer-managed keys only); DMS needs kms:Decrypt."
  type        = list(string)
  default     = []
}

variable "ssl_mode" {
  description = "Endpoint SSL mode; plain connections are not allowed."
  type        = string
  default     = "verify-full"

  validation {
    condition     = contains(["require", "verify-ca", "verify-full"], var.ssl_mode)
    error_message = "ssl_mode must be require, verify-ca or verify-full."
  }
}

variable "source_certificate_arn" {
  description = "DMS certificate (aws_dms_certificate) used to verify the source server (verify-ca/verify-full)."
  type        = string
  default     = null
}

variable "target_certificate_arn" {
  description = "DMS certificate used to verify the target server (verify-ca/verify-full)."
  type        = string
  default     = null
}

variable "source_extra_connection_attributes" {
  description = "Extra connection attributes for the source (e.g. Oracle 'useLogminerReader=N;useBfile=Y')."
  type        = string
  default     = ""
}

variable "target_extra_connection_attributes" {
  type    = string
  default = ""
}

# ------------------------------------------------------------------------- task
variable "migration_type" {
  description = "full-load, cdc or full-load-and-cdc."
  type        = string
  default     = "full-load-and-cdc"

  validation {
    condition     = contains(["full-load", "cdc", "full-load-and-cdc"], var.migration_type)
    error_message = "migration_type must be full-load, cdc or full-load-and-cdc."
  }
}

variable "table_mappings" {
  description = "DMS table-mapping JSON. Default: include every table of var.include_schema."
  type        = string
  default     = null
}

variable "include_schema" {
  description = "Schema included by the default table mapping."
  type        = string
  default     = "%"
}

variable "replication_task_settings" {
  description = "Task settings JSON (null = module defaults: logging on, limited LOB mode, validation on)."
  type        = string
  default     = null
}

variable "lob_max_size_kb" {
  description = "Limited-LOB-mode max LOB size used by the default task settings."
  type        = number
  default     = 32
}

# ------------------------------------------------------------------------- encryption / IAM
variable "kms_key_arn" {
  description = "KMS key for the replication instance, endpoints and logs (null = create one)."
  type        = string
  default     = null
}

variable "create_dms_service_roles" {
  description = "Create the account-wide dms-vpc-role and dms-cloudwatch-logs-role (only once per account)."
  type        = bool
  default     = false
}

variable "permissions_boundary_arn" {
  description = "Permission boundary attached to every IAM role (required by the OPA plan gate)."
  type        = string
}

# ------------------------------------------------------------------------- monitoring
variable "cdc_latency_threshold_seconds" {
  description = "Alarm when CDCLatencySource or CDCLatencyTarget exceeds this many seconds."
  type        = number
  default     = 300
}

variable "cdc_latency_evaluation_periods" {
  description = "Consecutive 5-minute periods above the threshold before alarming."
  type        = number
  default     = 3
}

variable "alarm_actions" {
  description = "SNS topic ARNs notified on alarm / OK."
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  type    = number
  default = 90
}

variable "tags" {
  type    = map(string)
  default = {}
}
