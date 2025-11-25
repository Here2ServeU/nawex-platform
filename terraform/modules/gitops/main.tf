terraform {
  required_version = ">= 1.3.0"
  required_providers {
    helm = { source = "hashicorp/helm", version = "~> 2.13" }
  }
}

provider "helm" {
  kubernetes {
    host                   = var.cluster_endpoint
    cluster_ca_certificate = base64decode(var.cluster_ca)
    token                  = var.cluster_token
  }
}

resource "helm_release" "argocd" {
  name             = "argocd"
  namespace        = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = "6.7.4"
  create_namespace = true

  values = []
}

# Placeholder for ArgoCD Application for Express v7
# You can alternatively use kubernetes_manifest.
