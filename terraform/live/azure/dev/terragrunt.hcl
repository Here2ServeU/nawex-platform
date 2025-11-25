inputs = {
  cloud       = "azure"
  environment = "dev"

  backend_config = {
    resource_group_name  = "rg-tf-backend"
    storage_account_name = "tfstateacctdev11202025"
    container_name       = "tfstate"
    key                  = "azure/dev.tfstate"
  }
}
