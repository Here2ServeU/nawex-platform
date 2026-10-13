# ------------------------------------------------------------------------------
# Karpenter (optional, var.karpenter_enabled)
# ------------------------------------------------------------------------------
# Just-in-time node provisioning. The managed "general" node group keeps running
# the controller and system add-ons; Karpenter provisions everything else from
# the NodePools / EC2NodeClass in deploy/k8s/platform-addons/karpenter/.
#
#   * controller IAM role (IRSA, kube-system:karpenter) + v1 controller policy
#   * node IAM role + instance profile + EKS access entry
#   * SQS interruption queue fed by EventBridge (spot interruption, rebalance,
#     instance state change, AWS Health)
# Every IAM role carries var.permissions_boundary_arn.
# ------------------------------------------------------------------------------

module "karpenter" {
  count   = var.karpenter_enabled ? 1 : 0
  source  = "terraform-aws-modules/eks/aws//modules/karpenter"
  version = "~> 20.24" # same major as module.eks; 20.24+ ships the Karpenter v1 policy

  cluster_name          = module.eks.cluster_name
  enable_v1_permissions = true

  # IRSA (consistent with the other controllers in this module) instead of
  # EKS Pod Identity.
  enable_irsa                     = true
  enable_pod_identity             = false
  create_pod_identity_association = false
  irsa_oidc_provider_arn          = module.eks.oidc_provider_arn
  irsa_namespace_service_accounts = ["kube-system:karpenter"]

  iam_role_name                     = "${var.name}-karpenter"
  iam_role_use_name_prefix          = false
  iam_role_permissions_boundary_arn = var.permissions_boundary_arn

  node_iam_role_name                 = "${var.name}-karpenter-node"
  node_iam_role_use_name_prefix      = false
  node_iam_role_permissions_boundary = var.permissions_boundary_arn
  node_iam_role_additional_policies = {
    AmazonSSMManagedInstanceCore = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }

  queue_name = "${var.name}-karpenter"

  tags = var.tags
}

resource "helm_release" "karpenter" {
  count      = var.karpenter_enabled ? 1 : 0
  name       = "karpenter"
  namespace  = "kube-system"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  version    = var.karpenter_chart_version

  values = [yamlencode({
    serviceAccount = {
      name = "karpenter"
      annotations = {
        "eks.amazonaws.com/role-arn" = module.karpenter[0].iam_role_arn
      }
    }
    settings = {
      clusterName       = module.eks.cluster_name
      clusterEndpoint   = module.eks.cluster_endpoint
      interruptionQueue = module.karpenter[0].queue_name
    }
    # Never schedule the controller onto nodes it manages.
    affinity = {
      nodeAffinity = {
        requiredDuringSchedulingIgnoredDuringExecution = {
          nodeSelectorTerms = [{
            matchExpressions = [{ key = "karpenter.sh/nodepool", operator = "DoesNotExist" }]
          }]
        }
      }
    }
    controller = {
      resources = {
        requests = { cpu = "250m", memory = "512Mi" }
        limits   = { cpu = "1", memory = "1Gi" }
      }
    }
  })]

  depends_on = [module.eks, module.karpenter]
}
