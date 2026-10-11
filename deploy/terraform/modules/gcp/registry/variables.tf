variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "repository_id" {
  description = "Artifact Registry repository ID (usually the project prefix)."
  type        = string
  default     = "golden"
}

variable "keep_images" {
  type    = number
  default = 30
}

variable "labels" {
  type    = map(string)
  default = {}
}
