provider "aws" {
  region = var.aws_region
}

# Customer-managed key for state objects and the lock table.
resource "aws_kms_key" "tf_backend" {
  description         = "Terraform state encryption (${var.bucket_name})"
  enable_key_rotation = true
}

resource "aws_kms_alias" "tf_backend" {
  name          = "alias/${var.bucket_name}"
  target_key_id = aws_kms_key.tf_backend.key_id
}

resource "aws_s3_bucket" "tf_backend" {
  bucket        = var.bucket_name
  force_destroy = false

  tags = {
    Name        = "Terraform Backend Bucket"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_versioning" "tf_backend_versioning" {
  bucket = aws_s3_bucket.tf_backend.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_backend" {
  bucket = aws_s3_bucket.tf_backend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.tf_backend.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "tf_backend" {
  bucket                  = aws_s3_bucket.tf_backend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "tf_lock" {
  name         = var.lock_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.tf_backend.arn
  }

  point_in_time_recovery {
    enabled = true
  }
}
