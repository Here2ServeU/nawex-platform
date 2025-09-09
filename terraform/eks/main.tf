############################
# Provider
############################
provider "aws" {
  region = var.region
}

############################
# VPC
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

  # Required tags for ALB controller/VPC discovery
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
# EKS (managed node group)
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
# Providers that use the EKS endpoint
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
# IRSA for AWS Load Balancer Controller
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

# AWS published policy JSON for the controller (bundled in repo)
resource "aws_iam_policy" "alb_controller" {
  name   = "${var.name}-AWSLoadBalancerControllerIAMPolicy"
  policy = file("${path.module}/policies/aws-load-balancer-controller.json")
}

resource "aws_iam_role_policy_attachment" "alb_attach" {
  role       = aws_iam_role.alb_irsa.name
  policy_arn = aws_iam_policy.alb_controller.arn
}

############################
# Chart values (yamlencode avoids dotted-key escaping issues)
############################
locals {
  # AWS Load Balancer Controller values
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

  # ingress-nginx values (public LoadBalancer)
  # Optionally disable admission webhooks to avoid slow/fragile first installs
  nginx_values = {
    controller = {
      service = {
        type = "LoadBalancer"
        annotations = {
          "service.beta.kubernetes.io/aws-load-balancer-scheme" = "internet-facing"
        }
      }
      admissionWebhooks = {
        enabled = false
      }
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
  depends_on       = [module.eks, aws_iam_role_policy_attachment.alb_attach]

  values  = [yamlencode(local.alb_values)]
  wait    = true
  timeout = 600
}

############################
# Ensure local kubeconfig is set & API is reachable
############################
resource "null_resource" "update_kubeconfig" {
  depends_on = [module.eks]

  triggers = {
    cluster  = module.eks.cluster_name
    endpoint = module.eks.cluster_endpoint
    region   = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command = <<-EOT
      set -euo pipefail
      echo "Updating kubeconfig for ${module.eks.cluster_name} in ${var.region}..."
      aws eks update-kubeconfig --name "${module.eks.cluster_name}" --region "${var.region}" --alias "${module.eks.cluster_name}"

      echo "Checking API reachability..."
      for i in {1..60}; do
        if kubectl cluster-info >/dev/null 2>&1; then
          echo "Kubernetes API is reachable."
          exit 0
        fi
        echo "  API not reachable yet ($i/60); sleeping 5s..."
        sleep 5
      done
      echo "ERROR: Kubernetes API not reachable in time."
      exit 1
    EOT
  }
}

############################
# Wait for ALB webhook endpoints before installing ingress-nginx
############################
resource "null_resource" "wait_alb_webhook" {
  depends_on = [
    helm_release.aws_load_balancer_controller,
    null_resource.update_kubeconfig
  ]

  triggers = {
    cluster = module.eks.cluster_name
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command = <<-EOT
      set -euo pipefail

      echo "Waiting for aws-load-balancer-controller deployment to be ready..."
      kubectl -n kube-system rollout status deploy/aws-load-balancer-controller --timeout=5m

      echo "Waiting for aws-load-balancer-webhook-service endpoints..."
      for i in {1..60}; do
        READY=$(kubectl -n kube-system get endpoints aws-load-balancer-webhook-service \
          -o jsonpath='{.subsets[0].addresses[0].ip}' 2>/dev/null || true)
        if [[ -n "$${READY}" ]]; then
          echo "Webhook endpoints are ready: $${READY}"
          exit 0
        fi
        echo "  not ready yet ($i/60); sleeping 5s..."
        sleep 5
      done

      echo "ERROR: aws-load-balancer-webhook-service endpoints not ready in time."
      exit 1
    EOT
  }
}

############################
# Helm: ingress-nginx (non-blocking) + post-install waiter
############################
resource "helm_release" "ingress_nginx" {
  count            = var.enable_ingress ? 1 : 0
  name             = "ingress-nginx"
  namespace        = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = "4.11.2"
  create_namespace = true

  depends_on = [null_resource.wait_alb_webhook]

  values             = [yamlencode(local.nginx_values)]
  wait               = false            # don't block here
  atomic             = false
  dependency_update  = true
  timeout            = 300
}

resource "null_resource" "wait_ingress_nginx" {
  count = var.enable_ingress ? 1 : 0
  depends_on = [
    helm_release.ingress_nginx,
    null_resource.wait_alb_webhook
  ]

  triggers = {
    cluster = module.eks.cluster_name
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command = <<-EOT
      set -euo pipefail

      NS="ingress-nginx"
      DEPLOY="ingress-nginx-controller"
      SVC="ingress-nginx-controller"

      echo "Waiting for $DEPLOY to be Ready..."
      for i in {1..60}; do
        if kubectl -n "$NS" get deploy "$DEPLOY" >/dev/null 2>&1; then
          if kubectl -n "$NS" rollout status deploy/"$DEPLOY" --timeout=30s; then
            echo "Deployment is Ready."
            break
          fi
        fi
        echo "  not ready yet ($i/60); sleeping 10s..."
        sleep 10
      done

      if ! kubectl -n "$NS" rollout status deploy/"$DEPLOY" --timeout=10s; then
        echo "---- Deployment describe ----"
        kubectl -n "$NS" describe deploy "$DEPLOY" || true
        echo "---- Pod events ----"
        kubectl -n "$NS" get pods -l app.kubernetes.io/name=ingress-nginx -o name | xargs -r -n1 kubectl -n "$NS" describe || true
        echo "ERROR: ingress-nginx deployment did not become Ready in time."
        exit 1
      fi

      echo "Waiting for LoadBalancer hostname..."
      for i in {1..60}; do
        DNS=$(kubectl -n "$NS" get svc "$SVC" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)
        if [[ -n "$DNS" ]]; then
          echo "ALB/NLB hostname: $DNS"
          exit 0
        fi
        echo "  no hostname yet ($i/60); sleeping 10s..."
        sleep 10
      done

      echo "---- Service describe ----"
      kubectl -n "$NS" describe svc "$SVC" || true
      echo "ERROR: ingress-nginx Service did not receive an external hostname."
      exit 1
    EOT
  }
}

############################
# App namespace
############################
resource "kubernetes_namespace_v1" "apps" {
  metadata { name = "apps" }
  depends_on = [module.eks]
}
