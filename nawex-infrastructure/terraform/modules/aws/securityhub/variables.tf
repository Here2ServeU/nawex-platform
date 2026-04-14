variable "enabled" {
  type        = bool
  description = "Whether to enable SecurityHub."
  default     = true
}

variable "standards_arns" {
  type        = list(string)
  description = "SecurityHub standards ARNs to enable."
  default     = []
}
