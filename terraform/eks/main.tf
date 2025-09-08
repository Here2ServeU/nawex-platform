provider "aws" { region = var.region }

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

data "aws_iam_policy_document" "alb_irsa_assume" {
  statement {
    effect = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = replace(module.eks.oidc_provider, "https://", "") ~ ":sub"
      values   = ["system:serviceaccount:kube-system:aws-load-balancer-controller"]
    }
    condition {
      test     = "StringEquals"
      variable = replace(module.eks.oidc_provider, "https://", "") ~ ":aud"
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

resource "helm_release" "aws_load_balancer_controller" {
  name             = "aws-load-balancer-controller"
  namespace        = "kube-system"
  repository       = "https://aws.github.io/eks-charts"
  chart            = "aws-load-balancer-controller"
  version          = "1.7.2"
  create_namespace = false
  depends_on       = [module.eks, aws_iam_role_policy_attachment.alb_attach]

  set { name = "clusterName"; value = module.eks.cluster_name }
  set { name = "region"; value = var.region }
  set { name = "vpcId"; value = module.vpc.vpc_id }
  set { name = "serviceAccount.create"; value = "true" }
  set { name = "serviceAccount.name"; value = "aws-load-balancer-controller" }
  set { name = "serviceAccount.annotations.eks\.amazonaws\.com/role-arn"; value = aws_iam_role.alb_irsa.arn }
}

resource "helm_release" "nginx" {
  count            = var.enable_ingress ? 1 : 0
  name             = "ingress-nginx"
  namespace        = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = "4.11.2"
  create_namespace = true
  depends_on       = [module.eks]
  set { name = "controller.service.type"; value = "LoadBalancer" }
  set { name = "controller.service.annotations.service\.beta\.kubernetes\.io/aws-load-balancer-scheme"; value = "internet-facing" }
}

resource "kubernetes_namespace_v1" "apps" {
  metadata { name = "apps" }
  depends_on = [module.eks]
}
