variable "region" {
  type    = string
  default = "us-east-1"
}

variable "name" {
  type    = string
  default = "qs-eks"
}

variable "kubernetes_version" {
  type    = string
  default = "1.29"
}

variable "vpc_cidr" {
  type    = string
  default = "10.1.0.0/16"
}

variable "azs" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "public_subnets" {
  type    = list(string)
  default = ["10.1.0.0/20", "10.1.16.0/20"]
}

variable "private_subnets" {
  type    = list(string)
  default = ["10.1.32.0/20", "10.1.48.0/20"]
}

variable "enable_ingress" {
  type    = bool
  default = true
}

variable "tags" {
  type = map(string)
  default = {
    Project     = "Quickstart"
    Environment = "dev"
  }
}
