variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "labels" {
  type = map(string)
  default = {
    env = "shared-services"
  }
}
