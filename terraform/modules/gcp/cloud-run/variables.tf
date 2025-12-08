variable "service_name" {}
variable "region" {}
variable "image_name" {}
variable "environment" {
  default = "production"
}
variable "allow_public_access" {
  type    = bool
  default = true
}
