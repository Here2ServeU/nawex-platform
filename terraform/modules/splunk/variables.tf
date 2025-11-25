variable "cloud" {
  description = "Cloud provider (aws, azure, gcp, oci)"
  type        = string
}

variable "project" {
  description = "Project name for resource naming."
  type        = string
}

variable "subnet_id"         { description = "Subnet ID for Splunk VM.";        type = string }
variable "security_group_id" { description = "Security group for Splunk VM.";   type = string }
variable "instance_type"     { description = "Instance size/type for Splunk.";  type = string }
variable "ami_id"            { description = "AMI ID for Splunk VM (AWS).";     type = string }
variable "key_name"          { description = "SSH key name for Splunk VM.";     type = string }

variable "splunk_hec_token" {
  description = "Splunk HEC token."
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}
