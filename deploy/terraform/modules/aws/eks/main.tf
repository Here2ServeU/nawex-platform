# ------------------------------------------------------------------------------
# AWS EKS MODULE
# ------------------------------------------------------------------------------
# VPC + EKS (managed node groups, IRSA) + optional GPU node group + IRSA roles
# for the AWS Load Balancer Controller and the platform workload service
# account. Providers (aws, helm) are configured by the calling root module.
# ------------------------------------------------------------------------------

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_partition" "current" {}

locals {
  azs             = slice(data.aws_availability_zones.available.names, 0, var.az_count)
  public_subnets  = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 4, i)]
  private_subnets = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 4, i + 8)]
  oidc_issuer     = replace(module.eks.cluster_oidc_issuer_url, "https://", "")

  base_node_groups = {
    general = {
      instance_types = [var.node_instance_type]
      desired_size   = var.node_count
      min_size       = var.node_min_count
      max_size       = var.node_max_count
      labels         = { "workload-type" = "general" }
    }
  }

  gpu_node_groups = var.gpu_node_pool_enabled ? {
    gpu = {
      ami_type       = "AL2023_x86_64_NVIDIA"
      instance_types = [var.gpu_instance_type]
      desired_size   = var.gpu_node_count
      min_size       = 0
      max_size       = max(var.gpu_node_count, 1)
      labels         = { "nvidia.com/gpu.present" = "true" }
      taints = {
        gpu = {
          key    = "nvidia.com/gpu"
          value  = "present"
          effect = "NO_SCHEDULE"
        }
      }
    }
  } : {}
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.7"

  name            = var.name
  cidr            = var.vpc_cidr
  azs             = local.azs
  public_subnets  = local.public_subnets
  private_subnets = local.private_subnets

  enable_nat_gateway   = true
  single_nat_gateway   = var.single_nat_gateway
  enable_dns_hostnames = true

  # Required tags for Kubernetes / ALB subnet discovery
  public_subnet_tags = {
    "kubernetes.io/cluster/${var.name}" = "shared"
    "kubernetes.io/role/elb"            = "1"
  }
  # karpenter.sh/discovery lets the EC2NodeClass find subnets (only when enabled).
  private_subnet_tags = merge({
    "kubernetes.io/cluster/${var.name}" = "shared"
    "kubernetes.io/role/internal-elb"   = "1"
  }, var.karpenter_enabled ? { "karpenter.sh/discovery" = var.name } : {})

  tags = var.tags
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.29"

  cluster_name    = var.name
  cluster_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Public endpoint only when allow-listed CIDRs are given; otherwise private-only.
  cluster_endpoint_public_access       = length(var.api_server_authorized_cidrs) > 0
  cluster_endpoint_public_access_cidrs = var.api_server_authorized_cidrs
  cluster_endpoint_private_access      = true

  enable_irsa                              = true
  enable_cluster_creator_admin_permissions = true

  # Every role carries the org permission boundary (enforce-permission-boundary SCP).
  iam_role_permissions_boundary = var.permissions_boundary_arn
  eks_managed_node_group_defaults = {
    iam_role_permissions_boundary = var.permissions_boundary_arn
  }

  cluster_addons = {
    coredns                = {}
    kube-proxy             = {}
    vpc-cni                = {}
    eks-pod-identity-agent = {}
    aws-ebs-csi-driver = {
      service_account_role_arn = aws_iam_role.ebs_csi.arn
    }
  }

  eks_managed_node_groups = merge(local.base_node_groups, local.gpu_node_groups)

  # Karpenter-launched nodes join the shared node security group.
  node_security_group_tags = var.karpenter_enabled ? { "karpenter.sh/discovery" = var.name } : {}

  tags = var.tags
}

# ------------------------------------------------------------------------------
# IRSA helper
# ------------------------------------------------------------------------------
data "aws_iam_policy_document" "irsa_assume" {
  for_each = {
    alb      = "system:serviceaccount:kube-system:aws-load-balancer-controller"
    ebs      = "system:serviceaccount:kube-system:ebs-csi-controller-sa"
    workload = "system:serviceaccount:${var.workload_namespace}:${var.workload_service_account}"
  }

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
      values   = [each.value]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_issuer}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

# EBS CSI driver (gp3 volumes)
resource "aws_iam_role" "ebs_csi" {
  name                 = "${var.name}-ebs-csi"
  assume_role_policy   = data.aws_iam_policy_document.irsa_assume["ebs"].json
  permissions_boundary = var.permissions_boundary_arn
  tags                 = var.tags
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role       = aws_iam_role.ebs_csi.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

# Platform workload identity (annotate the `golden` ServiceAccount with this ARN).
# Attach least-privilege policies for the AWS APIs the services need.
resource "aws_iam_role" "workload" {
  name                 = "${var.name}-workload"
  assume_role_policy   = data.aws_iam_policy_document.irsa_assume["workload"].json
  permissions_boundary = var.permissions_boundary_arn
  tags                 = var.tags
}

resource "aws_iam_role_policy_attachment" "workload" {
  for_each   = toset(var.workload_policy_arns)
  role       = aws_iam_role.workload.name
  policy_arn = each.value
}

# ------------------------------------------------------------------------------
# AWS Load Balancer Controller (serves `ingressClassName: alb`)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "alb" {
  count                = var.enable_alb_controller ? 1 : 0
  name                 = "${var.name}-alb-irsa"
  assume_role_policy   = data.aws_iam_policy_document.irsa_assume["alb"].json
  permissions_boundary = var.permissions_boundary_arn
  tags                 = var.tags
}

resource "aws_iam_policy" "alb" {
  count  = var.enable_alb_controller ? 1 : 0
  name   = "${var.name}-AWSLoadBalancerControllerIAMPolicy"
  policy = file("${path.module}/policies/aws-load-balancer-controller.json")
  tags   = var.tags
}

resource "aws_iam_role_policy_attachment" "alb" {
  count      = var.enable_alb_controller ? 1 : 0
  role       = aws_iam_role.alb[0].name
  policy_arn = aws_iam_policy.alb[0].arn
}

resource "helm_release" "aws_load_balancer_controller" {
  count      = var.enable_alb_controller ? 1 : 0
  name       = "aws-load-balancer-controller"
  namespace  = "kube-system"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  version    = "1.8.4"

  values = [yamlencode({
    clusterName = module.eks.cluster_name
    region      = var.region
    vpcId       = module.vpc.vpc_id
    serviceAccount = {
      create = true
      name   = "aws-load-balancer-controller"
      annotations = {
        "eks.amazonaws.com/role-arn" = aws_iam_role.alb[0].arn
      }
    }
  })]

  depends_on = [module.eks, aws_iam_role_policy_attachment.alb]
}

# NVIDIA device plugin so pods can request nvidia.com/gpu.
resource "helm_release" "nvidia_device_plugin" {
  count      = var.gpu_node_pool_enabled ? 1 : 0
  name       = "nvidia-device-plugin"
  namespace  = "kube-system"
  repository = "https://nvidia.github.io/k8s-device-plugin"
  chart      = "nvidia-device-plugin"
  version    = "0.16.2"

  values = [yamlencode({
    nodeSelector = { "nvidia.com/gpu.present" = "true" }
    tolerations  = [{ key = "nvidia.com/gpu", operator = "Exists", effect = "NoSchedule" }]
  })]

  depends_on = [module.eks]
}
