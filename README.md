# Enterprise Case Study — Modernizing Express Web App v6 into a High-Scale Platform Using Terraform, EKS, GitOps, AIOps & FinOps

## Built by Emmanuel Naweji — Cloud, DevOps, SRE, FinOps & AI Engineer

---

# Executive Summary
This case study demonstrates how an Express.js backend was transformed into a **cloud‑native, enterprise-grade, globally scalable, self-healing platform** using Terraform, Amazon EKS, Helm, ArgoCD, Prometheus, Grafana, AIOps engines, DevSecOps, and FinOps governance.

The infrastructure mirrors patterns used by companies such as **Netflix, Riot Games, Epic Games, Roblox, Coinbase, Shopify, Disney+, and TikTok**.

---

# Business Problem
Legacy Express.js applications typically suffer from:
- Manual deployments
- No scalability or auto-healing
- No cost visibility (FinOps)
- No anomaly detection (AIOps)
- No GitOps governance
- Slow recovery during incidents
- No container security scanning

This leads to slow delivery, higher cost, outages, and poor user experience.

---

# Enterprise Transformation Strategy
We modernize the app using:
- **Terraform IaC**  
- **AWS EKS (Kubernetes)**  
- **Helm packaging**  
- **ArgoCD GitOps**  
- **Prometheus + Grafana Observability**  
- **AIOps Anomaly Detection Engine**  
- **FinOps Cost Governance**  
- **DevSecOps Scanning (Trivy)**  

This creates a cloud platform — not just a deployment.

---

# Project Structure
```
express-t2s-app-v6/
├── charts/
│   ├── express-web-app/
│   ├── aiops/
│   ├── grafana/
│   └── prometheus/
├── scripts/
│   ├── cleanup.sh
│   ├── finops-test.sh
│   ├── force_destroy.sh
│   ├── generate-traffic.sh
│   ├── port-forward-aiops.sh
│   └── trivy-scan.sh
├── argocd/
├── terraform/
│   ├── backend/
│   ├── ecr/
│   └── eks/
├── aiops-service/
├── app/
└── README.md
```

---

# Enterprise Architecture (Used by Netflix, Riot, Epic Games)
```
                   GitHub (Source of Truth)
                            │
                            ▼
                       ArgoCD GitOps
                  (Auto Sync + Drift Fixing)
                            │
                            ▼
          ┌─────────────────────────────────────────┐
          │            Amazon EKS Cluster           │
          └─────────────────────────────────────────┘
                │             │            │
                ▼             ▼            ▼
         Express App       AIOps      Prometheus/Grafana
                │             │            │
                ▼             ▼            ▼
          AWS ALB Ingress    Alerts   Dashboards / SLIs
```

---

# Real Companies Using Similar Infrastructure

| Company | Infra Pattern Used |
|--------|---------------------|
| Netflix | Kubernetes, GitOps, Prometheus, Terraform |
| Riot Games | Kubernetes-based microservices, observability |
| Epic Games | Autoscaling infra for global game events |
| Disney+ | EKS, Terraform IaC |
| Shopify | Kubernetes + FinOps for multi-tenant workloads |
| Roblox | High-scale multi-cloud Kubernetes |
| Coinbase | Terraform, Kubernetes, high-security pipelines |

This project aligns with all these patterns.

---

# Deployment Guide — Step-by-Step

## STEP 1 — Provision Terraform Backend
```bash
cd terraform/backend
terraform init
terraform apply -auto-approve
```

## STEP 2 — Build & Push Image to ECR
```bash
cd terraform/ecr
terraform init && terraform apply -auto-approve
bash build_and_push.sh
```

## STEP 3 — Create EKS Cluster
```bash
cd terraform/eks
terraform init
terraform apply -auto-approve
```

## STEP 4 — Configure kubectl
```bash
aws eks update-kubeconfig --region us-east-1 --name t2s-eks
```

## STEP 5 — Deploy Express App with Helm
```bash
helm upgrade --install express-web-app ./charts/express-web-app -n apps --create-namespace
```

## STEP 6 — Deploy Prometheus + Grafana
```bash
helm upgrade --install prometheus ./charts/prometheus -n monitoring --create-namespace
helm upgrade --install grafana ./charts/grafana -n monitoring
```

## STEP 7 — Deploy AIOps Engine
```bash
helm upgrade --install aiops ./charts/aiops -n aiops --create-namespace
```

## STEP 8 — Deploy ArgoCD (GitOps)
```bash
kubectl create namespace argocd
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
helm upgrade --install argocd argo/argo-cd -n argocd --set server.service.type=ClusterIP
```

## STEP 9 — Deploy GitOps App
```bash
kubectl apply -f argocd/express-web-app.yaml
```

ArgoCD now:
- Auto-syncs deployments
- Detects drift
- Self-heals apps

---

# Testing AIOps + FinOps

## AIOps — Traffic Simulation
```bash
bash scripts/generate-traffic.sh
```

## View AIOps Engine
```bash
bash scripts/port-forward-aiops.sh
```

## FinOps Testing
```bash
bash scripts/finops-test.sh
```

Expected:
- Cost anomalies detected
- Overprovisioned resources flagged
- Recommendations printed

---

# DevSecOps Security Scanning
```bash
bash scripts/trivy-scan.sh
```

Covers:
- Docker images
- Terraform IaC
- Helm charts
- Kubernetes manifests

---

# Cleanup (Safe Deletion)
```bash
bash scripts/cleanup.sh
```

Destroys:
- EKS cluster
- Node groups
- ALBs
- NAT GWs
- Endpoints
- Subnets
- Route tables
- SGs
- VPC

---

# Final Outcome
This modernization delivers:
- Enterprise-grade resiliency
- AIOps-driven incident reduction
- FinOps cost governance
- Fully automated deployments (GitOps)
- High scalability for global traffic
- Production-ready monitoring (SLIs/SLOs)
- DevSecOps vulnerability protection

---

# Author

**Emmanuel Naweji (2025)**  
Cloud | DevOps | SRE | FinOps | AI Engineer  
Building enterprise cloud platforms and training engineers into the top 1% through real‑world, automation-driven solutions.

![AWS Certified](https://img.shields.io/badge/AWS-Certified-blue?logo=amazonaws)
![Azure Solutions Architect](https://img.shields.io/badge/Azure-Solutions%20Architect-0078D4?logo=microsoftazure)
![CKA](https://img.shields.io/badge/Kubernetes-CKA-blue?logo=kubernetes)
![Terraform](https://img.shields.io/badge/IaC-Terraform-623CE4?logo=terraform)
![GitHub Actions](https://img.shields.io/badge/CI/CD-GitHub%20Actions-blue?logo=githubactions)
![GitLab CI](https://img.shields.io/badge/CI/CD-GitLab%20CI-FC6D26?logo=gitlab)
![Jenkins](https://img.shields.io/badge/CI/CD-Jenkins-D24939?logo=jenkins)
![Ansible](https://img.shields.io/badge/Automation-Ansible-red?logo=ansible)
![ArgoCD](https://img.shields.io/badge/GitOps-ArgoCD-orange?logo=argo)
![VMware](https://img.shields.io/badge/Virtualization-VMware-607078?logo=vmware)
![Linux](https://img.shields.io/badge/OS-Linux-black?logo=linux)
![FinOps](https://img.shields.io/badge/FinOps-Cost%20Optimization-green?logo=money)
![OpenAI](https://img.shields.io/badge/AI-OpenAI-ff9900?logo=openai)

