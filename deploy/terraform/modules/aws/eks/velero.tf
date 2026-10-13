# ------------------------------------------------------------------------------
# Velero backup / DR (optional, var.velero_enabled)
# ------------------------------------------------------------------------------
# KMS-encrypted, versioned, private S3 bucket for Kubernetes object backups and
# EBS snapshots for PersistentVolumes. Schedules live in
# deploy/k8s/platform-addons/velero/; procedure in
# ops/runbooks/playbooks/backup_restore_velero.md.
# ------------------------------------------------------------------------------

data "aws_caller_identity" "current" {
  count = var.velero_enabled ? 1 : 0
}

locals {
  velero_bucket = coalesce(var.velero_bucket_name, "${var.name}-velero-backups")
}

resource "aws_kms_key" "velero" {
  count                   = var.velero_enabled ? 1 : 0
  description             = "${var.name} Velero backups"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = var.tags
}

resource "aws_kms_alias" "velero" {
  count         = var.velero_enabled ? 1 : 0
  name          = "alias/${var.name}-velero"
  target_key_id = aws_kms_key.velero[0].key_id
}

resource "aws_s3_bucket" "velero" {
  count  = var.velero_enabled ? 1 : 0
  bucket = local.velero_bucket
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "velero" {
  count  = var.velero_enabled ? 1 : 0
  bucket = aws_s3_bucket.velero[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "velero" {
  count  = var.velero_enabled ? 1 : 0
  bucket = aws_s3_bucket.velero[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.velero[0].arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "velero" {
  count                   = var.velero_enabled ? 1 : 0
  bucket                  = aws_s3_bucket.velero[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "velero" {
  count  = var.velero_enabled ? 1 : 0
  bucket = aws_s3_bucket.velero[0].id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Velero expires backups itself (Schedule TTL); this only bounds how long
# overwritten/deleted object versions are kept for recovery.
resource "aws_s3_bucket_lifecycle_configuration" "velero" {
  count  = var.velero_enabled ? 1 : 0
  bucket = aws_s3_bucket.velero[0].id
  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.velero_noncurrent_version_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

data "aws_iam_policy_document" "velero_bucket" {
  count = var.velero_enabled ? 1 : 0
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.velero[0].arn,
      "${aws_s3_bucket.velero[0].arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "velero" {
  count      = var.velero_enabled ? 1 : 0
  bucket     = aws_s3_bucket.velero[0].id
  policy     = data.aws_iam_policy_document.velero_bucket[0].json
  depends_on = [aws_s3_bucket_public_access_block.velero]
}

data "aws_iam_policy_document" "velero_assume" {
  count = var.velero_enabled ? 1 : 0
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_issuer}:sub"
      values   = ["system:serviceaccount:${var.velero_namespace}:velero-server"]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_issuer}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "velero" {
  count                = var.velero_enabled ? 1 : 0
  name                 = "${var.name}-velero"
  assume_role_policy   = data.aws_iam_policy_document.velero_assume[0].json
  permissions_boundary = var.permissions_boundary_arn
  tags                 = var.tags
}

# Least privilege: this bucket only, this key only, EC2 snapshot APIs scoped to
# the region, and deletes limited to snapshots Velero tagged.
data "aws_iam_policy_document" "velero" {
  count = var.velero_enabled ? 1 : 0

  statement {
    sid       = "BucketList"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.velero[0].arn]
  }

  statement {
    sid = "BucketObjects"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts",
    ]
    resources = ["${aws_s3_bucket.velero[0].arn}/*"]
  }

  statement {
    sid       = "BackupKey"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:DescribeKey"]
    resources = [aws_kms_key.velero[0].arn]
  }

  statement {
    sid       = "DescribeEbs"
    actions   = ["ec2:DescribeVolumes", "ec2:DescribeSnapshots"]
    resources = ["*"] # Describe* does not support resource-level permissions
  }

  statement {
    sid     = "SnapshotAndRestoreEbs"
    actions = ["ec2:CreateSnapshot", "ec2:CreateVolume", "ec2:CreateTags"]
    resources = [
      "arn:${data.aws_partition.current.partition}:ec2:${var.region}::snapshot/*",
      "arn:${data.aws_partition.current.partition}:ec2:${var.region}:${data.aws_caller_identity.current[0].account_id}:volume/*",
    ]
  }

  statement {
    sid       = "DeleteVeleroSnapshots"
    actions   = ["ec2:DeleteSnapshot"]
    resources = ["arn:${data.aws_partition.current.partition}:ec2:${var.region}::snapshot/*"]
    condition {
      test     = "Null"
      variable = "aws:ResourceTag/velero.io/backup"
      values   = ["false"]
    }
  }
}

resource "aws_iam_policy" "velero" {
  count  = var.velero_enabled ? 1 : 0
  name   = "${var.name}-velero"
  policy = data.aws_iam_policy_document.velero[0].json
  tags   = var.tags
}

resource "aws_iam_role_policy_attachment" "velero" {
  count      = var.velero_enabled ? 1 : 0
  role       = aws_iam_role.velero[0].name
  policy_arn = aws_iam_policy.velero[0].arn
}

resource "helm_release" "velero" {
  count            = var.velero_enabled ? 1 : 0
  name             = "velero"
  namespace        = var.velero_namespace
  create_namespace = true
  repository       = "https://vmware-tanzu.github.io/helm-charts"
  chart            = "velero"
  version          = var.velero_chart_version

  values = [yamlencode({
    initContainers = [{
      name            = "velero-plugin-for-aws"
      image           = var.velero_aws_plugin_image
      imagePullPolicy = "IfNotPresent"
      volumeMounts    = [{ mountPath = "/target", name = "plugins" }]
    }]
    credentials = { useSecret = false } # IRSA, no static keys
    serviceAccount = {
      server = {
        name = "velero-server"
        annotations = {
          "eks.amazonaws.com/role-arn" = aws_iam_role.velero[0].arn
        }
      }
    }
    configuration = {
      backupStorageLocation = [{
        name     = "default"
        provider = "aws"
        bucket   = aws_s3_bucket.velero[0].id
        default  = true
        config = {
          region   = var.region
          kmsKeyId = aws_kms_alias.velero[0].name
        }
      }]
      volumeSnapshotLocation = [{
        name     = "default"
        provider = "aws"
        config   = { region = var.region }
      }]
    }
    # File-system backup (node agent) stays off: EBS snapshots cover gp3 PVs.
    deployNodeAgent = false
    metrics = {
      enabled        = true
      serviceMonitor = { enabled = var.velero_service_monitor_enabled }
    }
  })]

  depends_on = [module.eks, aws_iam_role_policy_attachment.velero]
}
