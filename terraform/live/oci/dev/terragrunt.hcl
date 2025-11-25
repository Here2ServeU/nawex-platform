inputs = {
  cloud       = "oci"
  environment = "dev"

  backend_config = {
    namespace      = "my-namespace"
    bucket         = "emmanuel-tf-state-11202025"
    key            = "oci/dev.tfstate"
    region         = "us-ashburn-1"
  }
}
