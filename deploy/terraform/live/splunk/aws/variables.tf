variable "region" { type = string }
variable "name" { type = string }
variable "vpc_id" { type = string }
variable "subnet_id" { type = string }
variable "ami" { type = string }
variable "instance_type" {
  type    = string
  default = "t3.large"
}
variable "key_name" { type = string }
variable "admin_password" {
  type      = string
  sensitive = true
}
variable "hec_token" {
  type      = string
  sensitive = true
}
variable "allowed_cidr" {
  type    = string
  default = "0.0.0.0/0"
}
