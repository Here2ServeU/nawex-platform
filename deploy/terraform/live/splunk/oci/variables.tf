variable "compartment_ocid" { type = string }
variable "ad" { type = string }
variable "shape" {
  type    = string
  default = "VM.Standard2.4"
}
variable "subnet_id" { type = string }
variable "image_ocid" { type = string }
variable "display_name" { type = string }
variable "admin_password" {
  type      = string
  sensitive = true
}
variable "hec_token" {
  type      = string
  sensitive = true
}
