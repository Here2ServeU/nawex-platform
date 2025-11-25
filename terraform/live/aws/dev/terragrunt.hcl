include {
  path = find_in_parent_folders()
}

inputs = {
  cloud       = "aws"
  environment = "dev"

  backend_config = {
    bucket         = "emmanuel-tf-state-11202025"
    dynamodb_table = "terraform-locks"
    region         = "us-east-1"
  }
}
