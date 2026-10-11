variable "name" { type = string }
variable "zone" { type = string }
variable "network" { type = string }
variable "subnetwork" { type = string }
variable "machine_type" {
  type    = string
  default = "e2-standard-4"
}
variable "image" { type = string }

variable "admin_password" {
  type      = string
  sensitive = true
}

variable "hec_token" {
  type      = string
  sensitive = true
}

variable "assign_public_ip" {
  description = "Attach an ephemeral external IP (not recommended)."
  type        = bool
  default     = false
}
