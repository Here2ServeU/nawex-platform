# ------------------------------------------------------------------------------
# AWS ECR MODULE
# ------------------------------------------------------------------------------
# One private, scan-on-push, immutable-tag repository per platform image:
#   <project>/golden-platform, <project>/golden-client-portal, <project>/golden-workload
# ------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_ecr_repository" "this" {
  for_each = toset(var.images)

  name                 = "${var.project}/${each.value}"
  image_tag_mutability = var.immutable_tags ? "IMMUTABLE" : "MUTABLE"
  force_delete         = var.force_delete

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last ${var.keep_images} images"
      action       = { type = "expire" }
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.keep_images
      }
    }]
  })
}
