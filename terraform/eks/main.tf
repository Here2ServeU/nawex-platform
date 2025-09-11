############################
# Providers & identity
############################
provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

############################
# VPC (public + private)
############################
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.7"

  name            = var.name
  cidr            = var.vpc_cidr
  azs             = var.azs
  public_subnets  = var.public_subnets
  private_subnets = var.private_subnets

  enable_nat_gateway = true
  single_nat_gateway = true

  # Required tags for k8s/ALB discovery
  public_subnet_tags = {
    "kubernetes.io/cluster/${var.name}" = "shared"
    "kubernetes.io/role/elb"            = "1"
  }
  private_subnet_tags = {
    "kubernetes.io/cluster/${var.name}" = "shared"
    "kubernetes.io/role/internal-elb"   = "1"
  }

  tags = var.tags
}

############################
# EKS (managed node groups + IRSA)
############################
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.8"

  cluster_name    = var.name
  cluster_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  enable_irsa                              = true
  enable_cluster_creator_admin_permissions = true

  eks_managed_node_groups = {
    default = {
      instance_types = ["t3.medium"]
      desired_size   = 2
      min_size       = 1
      max_size       = 3
      tags           = var.tags
    }
  }

  tags = var.tags
}

############################
# K8s/Helm providers (auth via token)
############################
data "aws_eks_cluster_auth" "this" {
  name       = module.eks.cluster_name
  depends_on = [module.eks]
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  token                  = data.aws_eks_cluster_auth.this.token
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}

############################
# IAM for AWS Load Balancer Controller (IRSA)
############################
data "aws_iam_policy_document" "alb_irsa_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.oidc_provider, "https://", "")}:sub"
      values   = ["system:serviceaccount:kube-system:aws-load-balancer-controller"]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.oidc_provider, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "alb_irsa" {
  name               = "${var.name}-alb-irsa"
  assume_role_policy = data.aws_iam_policy_document.alb_irsa_assume.json
  tags               = var.tags
}

resource "aws_iam_policy" "alb_controller" {
  name   = "${var.name}-AWSLoadBalancerControllerIAMPolicy"
  policy = file("${path.module}/policies/aws-load-balancer-controller.json")
}

resource "aws_iam_role_policy_attachment" "alb_attach" {
  role       = aws_iam_role.alb_irsa.name
  policy_arn = aws_iam_policy.alb_controller.arn
}

############################
# Helm values
############################
locals {
  alb_values = {
    clusterName = module.eks.cluster_name
    region      = var.region
    vpcId       = module.vpc.vpc_id
    serviceAccount = {
      create = true
      name   = "aws-load-balancer-controller"
      annotations = {
        "eks.amazonaws.com/role-arn" = aws_iam_role.alb_irsa.arn
      }
    }
  }

  nginx_values = {
    controller = {
      replicaCount = 2
      service = {
        enabled               = true
        type                  = "LoadBalancer"
        externalTrafficPolicy = "Cluster"
        annotations = {
          "service.beta.kubernetes.io/aws-load-balancer-type"            = "nlb"
          "service.beta.kubernetes.io/aws-load-balancer-scheme"          = "internet-facing"
          "service.beta.kubernetes.io/aws-load-balancer-nlb-target-type" = "ip"
        }
        ports = {
          http  = 80
          https = 443
        }
        targetPorts = {
          http  = "http"
          https = "https"
        }
      }
      admissionWebhooks = { enabled = false }
    }
  }
}

############################
# Helm: AWS Load Balancer Controller
############################
resource "helm_release" "aws_load_balancer_controller" {
  name             = "aws-load-balancer-controller"
  namespace        = "kube-system"
  repository       = "https://aws.github.io/eks-charts"
  chart            = "aws-load-balancer-controller"
  version          = "1.7.2"
  create_namespace = false

  depends_on = [module.eks, aws_iam_role_policy_attachment.alb_attach]

  values  = [yamlencode(local.alb_values)]
  wait    = true
  timeout = 600
}

############################
# Helm: ingress-nginx
############################
resource "helm_release" "ingress_nginx" {
  count            = var.enable_ingress ? 1 : 0
  name             = "ingress-nginx"
  namespace        = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = "4.11.2"
  create_namespace = true

  depends_on = [helm_release.aws_load_balancer_controller]

  values            = [yamlencode(local.nginx_values)]
  recreate_pods     = true
  force_update      = true
  cleanup_on_fail   = true
  wait              = false
  atomic            = false
  dependency_update = true
  timeout           = 300
}

############################
# App namespace
############################
resource "kubernetes_namespace_v1" "apps" {
  metadata { name = "apps" }
  depends_on = [module.eks]
}
