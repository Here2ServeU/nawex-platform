############################
# Providers
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
# Helm values (explicit ports to ensure NLB listeners)
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

  # ingress-nginx via internet-facing NLB (IP targets) with explicit ports
  nginx_values = {
    controller = {
      replicaCount = 2

      service = {
        enabled               = true
        type                  = "LoadBalancer"
        externalTrafficPolicy = "Cluster"
        annotations = {
          # NLB config
          "service.beta.kubernetes.io/aws-load-balancer-type"             = "nlb"
          "service.beta.kubernetes.io/aws-load-balancer-scheme"           = "internet-facing"
          "service.beta.kubernetes.io/aws-load-balancer-nlb-target-type"  = "ip"

          # (optional) make health checks explicit for NLB
          "service.beta.kubernetes.io/aws-load-balancer-healthcheck-protocol" = "TCP"
          "service.beta.kubernetes.io/aws-load-balancer-healthcheck-port"     = "traffic-port"
        }

        # EXPLICIT ports => ensures NLB creates listeners 80/443
        ports = {
          http  = 80
          https = 443
        }
        targetPorts = {
          http  = "http"
          https = "https"
        }
      }

      # Keep admission webhooks off initially to avoid race on fresh clusters
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

  depends_on = [module.eks, aws_iam_role_policy_attachment.alb_attach]

  values  = [yamlencode(local.alb_values)]
  wait    = true
  timeout = 600
}

############################
# Ensure local kubeconfig is usable (optional but handy)
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
      aws eks update-kubeconfig --name "${module.eks.cluster_name}" --region "${var.region}" --alias "${module.eks.cluster_name}"
      for i in {1..60}; do
        if kubectl cluster-info >/dev/null 2>&1; then
          echo "Kubernetes API is reachable."
          exit 0
        fi
        echo "API not reachable yet ($i/60); sleeping 5s..."; sleep 5
      done
      echo "ERROR: Kubernetes API not reachable in time."; exit 1
    EOT
  }
}

############################
# Wait for ALB webhook endpoints (prevents race)
############################
resource "null_resource" "wait_alb_webhook" {
  depends_on = [helm_release.aws_load_balancer_controller, null_resource.update_kubeconfig]

  triggers = { cluster = module.eks.cluster_name }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command = <<-EOT
      set -euo pipefail
      kubectl -n kube-system rollout status deploy/aws-load-balancer-controller --timeout=5m
      for i in {1..60}; do
        READY=$(kubectl -n kube-system get endpoints aws-load-balancer-webhook-service \
          -o jsonpath='{.subsets[0].addresses[0].ip}' 2>/dev/null || true)
        if [[ -n "$${READY}" ]]; then
          echo "ALB webhook endpoints ready: $${READY}"
          exit 0
        fi
        echo "Webhook not ready ($i/60); sleeping 5s..."; sleep 5
      done
      echo "ERROR: ALB webhook endpoints not ready in time."; exit 1
    EOT
  }
}

############################
# Helm: ingress-nginx (internet-facing NLB, IP targets)
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

  values            = [yamlencode(local.nginx_values)]
  recreate_pods     = true
  force_update      = true
  cleanup_on_fail   = true
  wait              = false
  atomic            = false
  dependency_update = true
  timeout           = 300
}

resource "null_resource" "wait_ingress_nginx" {
  count      = var.enable_ingress ? 1 : 0
  depends_on = [helm_release.ingress_nginx]

  triggers = { cluster = module.eks.cluster_name }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command = <<-EOT
      set -euo pipefail
      NS="ingress-nginx"; DEP="ingress-nginx-controller"; SVC="ingress-nginx-controller"

      echo "Waiting for controller rollout..."
      for i in {1..60}; do
        if kubectl -n "$NS" get deploy "$DEP" >/dev/null 2>&1 && \
           kubectl -n "$NS" rollout status deploy/"$DEP" --timeout=30s; then
          break
        fi
        echo "  not ready yet ($i/60); sleeping 10s..."; sleep 10
      done

      echo "Waiting for LB hostname..."
      for i in {1..60}; do
        DNS=$(kubectl -n "$NS" get svc "$SVC" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)
        if [[ -n "$DNS" ]]; then
          echo "Ingress LB hostname: $DNS"
          exit 0
        fi
        echo "  no hostname yet ($i/60); sleeping 10s..."; sleep 10
      done

      echo "---- Service describe ----"
      kubectl -n "$NS" describe svc "$SVC" || true
      echo "ERROR: ingress-nginx Service did not receive an external hostname."
      exit 1
    EOT
  }
}

############################
# Pre-destroy cleanup to avoid VPC/Subnet/IGW DependencyViolation
############################

resource "null_resource" "predestroy_lb_cleanup" {
  depends_on = [
    module.eks,
    module.vpc,
    helm_release.ingress_nginx,
    helm_release.aws_load_balancer_controller
  ]

  # Only pass values via triggers; destroy-time provisioner may only read self.*
  triggers = {
    region = var.region
    vpc_id = module.vpc.vpc_id
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["/bin/bash", "-lc"]
    command     = <<-EOT
      set -euo pipefail
      REGION="$${self.triggers.region}"
      VPC_ID="$${self.triggers.vpc_id}"

      echo "[CLEANUP] Start pre-destroy cleanup for VPC $VPC_ID in $REGION"

      # 0) Best-effort k8s/Helm cleanup; ignore failures if cluster is already down
      helm -n ingress-nginx uninstall ingress-nginx || true
      helm -n kube-system uninstall aws-load-balancer-controller || true

      echo "[CLEANUP] Deleting Kubernetes Services of type LoadBalancer..."
      SVCs=$(kubectl get svc -A -o jsonpath='{range .items[?(@.spec.type=="LoadBalancer")]}{.metadata.namespace}{" "}{.metadata.name}{"\n"}{end}' || true)
      if [[ -n "$SVCs" ]]; then
        while read -r ns name; do
          [[ -z "$ns" || -z "$name" ]] && continue
          echo "  - deleting svc $ns/$name"
          kubectl -n "$ns" delete svc "$name" --wait=false || true
        done <<< "$SVCs"
      fi

      # 1) Delete all ELBv2 (ALB/NLB) in this VPC (and listeners)
      echo "[CLEANUP] Deleting ELBv2 (ALB/NLB) in VPC..."
      for i in {1..30}; do
        ARNS=$(aws elbv2 describe-load-balancers --region "$REGION" \
          --query "LoadBalancers[?VpcId=='$VPC_ID'].LoadBalancerArn" --output text || true)
        [[ -n "$ARNS" ]] || { echo "  No ELBv2 found (ok)."; break; }
        for arn in $ARNS; do
          echo "  - deleting listeners for $arn"
          LST=$(aws elbv2 describe-listeners --region "$REGION" --load-balancer-arn "$arn" \
            --query "Listeners[].ListenerArn" --output text 2>/dev/null || true)
          for l in $LST; do aws elbv2 delete-listener --region "$REGION" --listener-arn "$l" || true; done
          echo "  - deleting load balancer $arn"
          aws elbv2 delete-load-balancer --region "$REGION" --load-balancer-arn "$arn" || true
        done
        echo "  Waiting for ELBv2 to disappear..."; sleep 10
      done

      # 2) Delete any Classic ELBs (rare but can block IGW)
      echo "[CLEANUP] Deleting Classic ELBs (if any) in VPC..."
      # Find classic ELBs by matching their subnets to our VPC
      CLB_NAMES=$(aws elb describe-load-balancers --region "$REGION" \
        --query "LoadBalancerDescriptions[?contains(Join('',Subnets),'')].LoadBalancerName" \
        --output text 2>/dev/null || true)
      if [[ -n "$CLB_NAMES" ]]; then
        # Narrow to names whose subnets belong to our VPC
        for name in $CLB_NAMES; do
          SUBNETS=$(aws elb describe-load-balancers --region "$REGION" --load-balancer-names "$name" \
            --query "LoadBalancerDescriptions[0].Subnets" --output text 2>/dev/null || true)
          MATCH=0
          for s in $SUBNETS; do
            SVPC=$(aws ec2 describe-subnets --region "$REGION" --subnet-ids "$s" \
              --query "Subnets[0].VpcId" --output text 2>/dev/null || true)
            [[ "$SVPC" == "$VPC_ID" ]] && MATCH=1
          done
          if [[ "$MATCH" == "1" ]]; then
            echo "  - deleting Classic ELB $name"
            aws elb delete-load-balancer --region "$REGION" --load-balancer-name "$name" || true
          fi
        done
      else
        echo "  No Classic ELBs found (ok)."
      fi

      # 3) Delete orphaned Target Groups (left by Services/Ingress)
      echo "[CLEANUP] Deleting orphaned Target Groups..."
      TGS=$(aws elbv2 describe-target-groups --region "$REGION" \
        --query "TargetGroups[?VpcId=='$VPC_ID'].TargetGroupArn" --output text || true)
      for tg in $TGS; do aws elbv2 delete-target-group --region "$REGION" --target-group-arn "$tg" || true; done

      # 4) Delete NAT Gateways and record their EIP AllocationIds
      echo "[CLEANUP] Deleting NAT Gateways in VPC (if any) and capturing EIPs..."
      NAT_EIPS=""
      NGWS=$(aws ec2 describe-nat-gateways --region "$REGION" \
        --filter Name=vpc-id,Values="$VPC_ID" \
        --query "NatGateways[].NatGatewayId" --output text || true)
      for ngw in $NGWS; do
        # collect EIP allocation ids tied to this NAT
        ALLOCS=$(aws ec2 describe-nat-gateways --region "$REGION" --nat-gateway-ids "$ngw" \
          --query "NatGateways[0].NatGatewayAddresses[].AllocationId" --output text || true)
        NAT_EIPS="$NAT_EIPS $ALLOCS"
        echo "  - deleting NAT Gateway $ngw"
        aws ec2 delete-nat-gateway --region "$REGION" --nat-gateway-id "$ngw" || true
      done

      # wait for NATs to be fully gone
      for i in {1..30}; do
        NGW_LEFT=$(aws ec2 describe-nat-gateways --region "$REGION" \
          --filter Name=vpc-id,Values="$VPC_ID" Name=state,Values=pending,available,deleting \
          --query "NatGateways[].NatGatewayId" --output text || true)
        [[ -z "$NGW_LEFT" ]] && { echo "  NAT Gateways gone."; break; }
        echo "  Waiting for NAT GW deletion..."; sleep 10
      done

      # Release the NAT EIPs
      if [[ -n "$NAT_EIPS" ]]; then
        echo "[CLEANUP] Releasing EIPs used by NAT Gateways..."
        for alloc in $NAT_EIPS; do
          [[ -z "$alloc" || "$alloc" == "None" ]] && continue
          # disassociate if still associated, then release
          ASSOC=$(aws ec2 describe-addresses --region "$REGION" --allocation-ids "$alloc" \
            --query "Addresses[0].AssociationId" --output text 2>/dev/null || true)
          [[ "$ASSOC" != "None" ]] && aws ec2 disassociate-address --region "$REGION" --association-id "$ASSOC" || true
          aws ec2 release-address --region "$REGION" --allocation-id "$alloc" || true
        done
      fi

      # 5) Disassociate & release any other EIPs attached to ENIs in this VPC
      echo "[CLEANUP] Releasing any other EIPs associated to ENIs in this VPC..."
      ENIS=$(aws ec2 describe-network-interfaces --region "$REGION" \
        --filters Name=vpc-id,Values="$VPC_ID" \
        --query "NetworkInterfaces[].{Id:NetworkInterfaceId,Assoc:Association}" --output json || echo "[]")
      echo "$ENIS" | jq -r '.[] | select(.Assoc!=null and .Assoc.PublicIp!=null) | [.Id, .Assoc.AssociationId, .Assoc.PublicIp] | @tsv' | while IFS=$'\t' read -r eni assoc pub; do
        echo "  - ENI $eni has EIP $pub (assoc $assoc); disassociating..."
        [[ -n "$assoc" && "$assoc" != "null" ]] && aws ec2 disassociate-address --region "$REGION" --association-id "$assoc" || true
      done

      # After disassociation, release any unattached EIPs in this VPC (heuristic: those whose network interface belongs to VPC)
      ADDRS=$(aws ec2 describe-addresses --region "$REGION" --query "Addresses[]" --output json || echo "[]")
      echo "$ADDRS" | jq -r '.[] | select(.NetworkInterfaceId!=null) | [.AllocationId, .NetworkInterfaceId] | @tsv' | while IFS=$'\t' read -r alloc eni; do
        # Check if ENI is in our VPC
        EVPC=$(aws ec2 describe-network-interfaces --region "$REGION" --network-interface-ids "$eni" \
          --query "NetworkInterfaces[0].VpcId" --output text 2>/dev/null || true)
        [[ "$EVPC" == "$VPC_ID" ]] || continue
        # Try to release if no longer associated
        ASSOC=$(aws ec2 describe-addresses --region "$REGION" --allocation-ids "$alloc" \
          --query "Addresses[0].AssociationId" --output text 2>/dev/null || true)
        if [[ "$ASSOC" == "None" || -z "$ASSOC" || "$ASSOC" == "null" ]]; then
          echo "  - releasing EIP allocation $alloc (was tied to ENI $eni)"
          aws ec2 release-address --region "$REGION" --allocation-id "$alloc" || true
        fi
      done

      # 6) Wait until no ELB/NAT related ENIs remain
      echo "[CLEANUP] Waiting for ELB/NAT ENIs to be gone..."
      for i in {1..30}; do
        ENIS_LEFT=$(aws ec2 describe-network-interfaces --region "$REGION" \
          --filters Name=vpc-id,Values="$VPC_ID" \
          --query "NetworkInterfaces[?contains(Description, 'ELB') || contains(Description, 'elb') || contains(Description, 'nat') || contains(Description, 'Load Balancer')].NetworkInterfaceId" \
          --output text || true)
        [[ -z "$ENIS_LEFT" ]] && { echo "  No ELB/NAT ENIs remain (ok)."; break; }
        echo "  Remaining ENIs: $ENIS_LEFT"; sleep 10
      done

      # 7) (Optional) Turn off auto-assign public IP on public subnets to avoid new mappings during destroy window
      echo "[CLEANUP] Disabling mapPublicIpOnLaunch on public subnets (best-effort)..."
      PUBS=$(aws ec2 describe-subnets --region "$REGION" \
        --filters Name=vpc-id,Values="$VPC_ID" Name=tag:kubernetes.io/role/elb,Values=1 \
        --query "Subnets[].SubnetId" --output text || true)
      for s in $PUBS; do
        aws ec2 modify-subnet-attribute --region "$REGION" --subnet-id "$s" --no-map-public-ip-on-launch || true
      done

      echo "[CLEANUP] Done. Terraform can detach the IGW and delete public subnets now."
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
