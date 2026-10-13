variable "name" { type = string }
variable "location" { type = string }
variable "resource_group" { type = string }
variable "subnet_id" { type = string }
variable "vm_size" {
  type    = string
  default = "Standard_D4s_v3"
}
variable "ssh_public_key" { type = string }
variable "admin_password" {
  type      = string
  sensitive = true
}
variable "hec_token" {
  type      = string
  sensitive = true
}
