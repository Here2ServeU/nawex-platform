variable "name" {
  description = "Cluster identifier and prefix for instances, parameter groups, proxy and alarms (lowercase, hyphens)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,40}$", var.name))
    error_message = "name must start with a letter and contain only lowercase letters, digits and hyphens (max 41)."
  }
}

variable "subnet_ids" {
  description = "Private subnets (at least two AZs) for the cluster and RDS Proxy."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "Provide at least two subnets in different AZs."
  }
}

variable "security_group_ids" {
  description = "Security groups for the cluster and proxy (allow 5432 from app / PgBouncer / proxy security groups only)."
  type        = list(string)
}

# ------------------------------------------------------------------------- engine
variable "engine_version" {
  description = "Aurora PostgreSQL engine version; the parameter group family is derived from the major version."
  type        = string
  default     = "16.4"
}

variable "database_name" {
  description = "Initial database name."
  type        = string
  default     = "app"
}

variable "master_username" {
  description = "Master user name (password managed by Secrets Manager). Applications should use their own roles."
  type        = string
  default     = "golden_admin"
}

variable "instance_class" {
  description = "Instance class for writer and readers. Size with `golden db capacity` (prefer Graviton r7g/r6g)."
  type        = string
  default     = "db.r7g.large"
}

variable "instance_count" {
  description = "Instances managed by Terraform: 1 writer + (n-1) readers. Use >= 2 in production for failover."
  type        = number
  default     = 2

  validation {
    condition     = var.instance_count >= 1 && var.instance_count <= 16
    error_message = "instance_count must be between 1 and 16."
  }
}

variable "io_optimized" {
  description = "Use Aurora I/O-Optimized storage (aurora-iopt1). Worth it when I/O is >= ~25% of the cluster bill."
  type        = bool
  default     = false
}

variable "kms_key_arn" {
  description = "Existing KMS key for storage, Performance Insights and the master secret; null creates one."
  type        = string
  default     = null
}

variable "apply_immediately" {
  description = "Apply modifications immediately instead of in the maintenance window."
  type        = bool
  default     = false
}

# ------------------------------------------------------------------------- tuning (documented in docs/database/README.md)
variable "log_min_duration_statement_ms" {
  description = "Log statements slower than this many ms (-1 disables). 250-1000 ms for OLTP."
  type        = number
  default     = 500
}

variable "auto_explain_min_duration_ms" {
  description = "auto_explain logs the plan (JSON, buffers, row counts) of statements slower than this many ms."
  type        = number
  default     = 1000
}

variable "idle_in_transaction_timeout_ms" {
  description = "Terminate sessions idle inside an open transaction for longer than this (they hold locks and block vacuum)."
  type        = number
  default     = 60000
}

variable "random_page_cost" {
  description = "Planner cost of a random page read; 1.1 for SSD-backed Aurora storage (default 4.0 assumes spinning disks)."
  type        = number
  default     = 1.1
}

variable "work_mem_kb" {
  description = "work_mem in kB (per sort/hash node per connection). From `golden db capacity` memory_parameters."
  type        = number
  default     = 16384
}

variable "maintenance_work_mem_kb" {
  description = "maintenance_work_mem in kB (VACUUM, CREATE INDEX). ~5% of RAM, up to 2GB."
  type        = number
  default     = 1048576
}

variable "extra_cluster_parameters" {
  description = "Additional cluster parameters."
  type = list(object({
    name         = string
    value        = string
    apply_method = string
  }))
  default = []
}

variable "extra_instance_parameters" {
  description = "Additional instance parameters."
  type = list(object({
    name         = string
    value        = string
    apply_method = string
  }))
  default = []
}

# ------------------------------------------------------------------------- backup / protection
variable "backup_retention_days" {
  description = "Automated backup retention (1-35 days)."
  type        = number
  default     = 14

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be between 1 and 35."
  }
}

variable "preferred_backup_window" {
  description = "Daily backup window (UTC)."
  type        = string
  default     = "03:00-04:00"
}

variable "preferred_maintenance_window" {
  description = "Weekly maintenance window (UTC); must not overlap the backup window."
  type        = string
  default     = "sun:04:30-sun:05:30"
}

variable "deletion_protection" {
  description = "Block cluster deletion."
  type        = bool
  default     = true
}

# ------------------------------------------------------------------------- observability
variable "performance_insights_retention_days" {
  description = "Performance Insights retention: 7 (free tier) or a multiple of 31 up to 731."
  type        = number
  default     = 7

  validation {
    condition     = var.performance_insights_retention_days == 7 || (var.performance_insights_retention_days % 31 == 0 && var.performance_insights_retention_days <= 731)
    error_message = "performance_insights_retention_days must be 7 or a multiple of 31 up to 731."
  }
}

variable "monitoring_interval" {
  description = "Enhanced Monitoring interval in seconds (0 disables)."
  type        = number
  default     = 30

  validation {
    condition     = contains([0, 1, 5, 10, 15, 30, 60], var.monitoring_interval)
    error_message = "monitoring_interval must be one of 0, 1, 5, 10, 15, 30, 60."
  }
}

# ------------------------------------------------------------------------- RDS Proxy
variable "enable_proxy" {
  description = "Create an RDS Proxy (connection pooling and faster failover) in front of the cluster."
  type        = bool
  default     = true
}

variable "proxy_auth_secret_arns" {
  description = "Secrets Manager secrets (one per database user) the proxy may use; empty uses the managed master secret."
  type        = list(string)
  default     = []
}

variable "proxy_iam_auth" {
  description = "Require IAM authentication from clients to the proxy (REQUIRED or DISABLED)."
  type        = string
  default     = "REQUIRED"

  validation {
    condition     = contains(["REQUIRED", "DISABLED"], var.proxy_iam_auth)
    error_message = "proxy_iam_auth must be REQUIRED or DISABLED."
  }
}

variable "proxy_max_connections_percent" {
  description = "Max share of max_connections the proxy opens (leave headroom for admin and migrations)."
  type        = number
  default     = 80
}

variable "proxy_max_idle_connections_percent" {
  description = "Idle server connections the proxy keeps warm, as a share of max_connections."
  type        = number
  default     = 40
}

variable "proxy_connection_borrow_timeout" {
  description = "Seconds a client waits for a pooled connection before an error."
  type        = number
  default     = 30
}

variable "proxy_idle_client_timeout" {
  description = "Seconds before the proxy closes an idle client connection."
  type        = number
  default     = 1800
}

# ------------------------------------------------------------------------- reader auto scaling
variable "reader_autoscaling_enabled" {
  description = "Scale Aurora readers with Application Auto Scaling (needs instance_count >= 2)."
  type        = bool
  default     = false
}

variable "reader_min_capacity" {
  description = "Minimum readers when auto scaling."
  type        = number
  default     = 1
}

variable "reader_max_capacity" {
  description = "Maximum readers when auto scaling (Aurora allows up to 15)."
  type        = number
  default     = 5
}

variable "reader_autoscaling_metric" {
  description = "Target-tracking metric: cpu (RDSReaderAverageCPUUtilization) or connections (RDSReaderAverageDatabaseConnections)."
  type        = string
  default     = "cpu"

  validation {
    condition     = contains(["cpu", "connections"], var.reader_autoscaling_metric)
    error_message = "reader_autoscaling_metric must be cpu or connections."
  }
}

variable "reader_autoscaling_target" {
  description = "Target value: average reader CPU % or connections per reader."
  type        = number
  default     = 60
}

variable "reader_scale_in_cooldown" {
  description = "Seconds after a scale-in before another scaling activity."
  type        = number
  default     = 600
}

variable "reader_scale_out_cooldown" {
  description = "Seconds after a scale-out before another scaling activity."
  type        = number
  default     = 300
}

# ------------------------------------------------------------------------- alarms
variable "alarm_actions" {
  description = "SNS topic ARNs notified on alarm / OK."
  type        = list(string)
  default     = []
}

variable "alarm_evaluation_periods" {
  description = "Consecutive 5-minute periods before an instance alarm fires."
  type        = number
  default     = 3
}

variable "cpu_alarm_threshold" {
  description = "CPUUtilization % alarm threshold."
  type        = number
  default     = 80
}

variable "freeable_memory_alarm_bytes" {
  description = "Alarm when FreeableMemory drops below this many bytes."
  type        = number
  default     = 1073741824
}

variable "max_connections" {
  description = "Effective max_connections of the instance class (SHOW max_connections) used for the saturation alarm."
  type        = number
  default     = 1000
}

variable "connection_alarm_ratio" {
  description = "Alarm when DatabaseConnections exceeds this fraction of max_connections."
  type        = number
  default     = 0.8
}

variable "replica_lag_alarm_ms" {
  description = "AuroraReplicaLag alarm threshold in milliseconds."
  type        = number
  default     = 1000
}

variable "deadlock_alarm_threshold" {
  description = "Alarm when Deadlocks (sum per 5 minutes) exceeds this value."
  type        = number
  default     = 0
}

variable "xid_age_alarm_threshold" {
  description = "MaximumUsedTransactionIDs alarm threshold (wraparound hard limit is ~2.1 billion)."
  type        = number
  default     = 1000000000
}

# ------------------------------------------------------------------------- governance
variable "permissions_boundary_arn" {
  description = "Permission boundary attached to every IAM role (required by the OPA plan gate)."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
