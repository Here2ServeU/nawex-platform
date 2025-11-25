module "splunk" {
  source = "../../../modules/splunk"
  cloud            = var.cloud
  environment      = var.environment
  subnet_id        = module.network.subnet_id
  security_group_id = module.network.sg_id
}
