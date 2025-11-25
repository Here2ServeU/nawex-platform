
# Enterprise Case Study — Modernizing Express Web App v6  
## Terraform • Amazon EKS • Helm • ArgoCD GitOps • AIOps • DevSecOps • FinOps  
### **Built by Emmanuel Naweji — Cloud | DevOps | SRE | FinOps | AI Engineer**

---

# Executive Summary
This case study demonstrates how a legacy Express.js backend was transformed into a **cloud‑native, enterprise-grade, globally scalable, self-healing platform** using Terraform, Amazon EKS, Helm, ArgoCD GitOps, Prometheus, Grafana, AIOps automation, DevSecOps pipelines, and FinOps cost governance.

The infrastructure mirrors real-world patterns used by:
- **Netflix**
- **Riot Games**
- **Epic Games**
- **Roblox**
- **Disney+**
- **Shopify**
- **Coinbase**

These companies rely on Kubernetes, GitOps, IaC, AIOps, and FinOps at massive scale—the same patterns implemented in this project.

---

# Business Problem
Legacy Express.js apps typically suffer from:
- Manual deployments  
- No autoscaling or resilience  
- No centralized monitoring  
- No anomaly detection  
- No cost visibility  
- No GitOps consistency  
- No DevSecOps scanning  

This results in outages, slow delivery, high cost, and unreliable operations.

---

# Enterprise Transformation Strategy
We redesigned the system using:

### **Cloud & Orchestration**
- AWS EKS (Managed Kubernetes)
- VPC, Subnets, NAT, ALB

### **IaC**
- Terraform for all infrastructure

### **Application Deployment**
- Helm chart packaging  
- ArgoCD GitOps automation  

### **Observability**
- Prometheus Operator  
- AlertManager  
- Grafana dashboards  

### **AIOps**
- Custom anomaly detection  
- Traffic simulation  
- Latency/error-rate monitoring  

### **FinOps**
- Pod-level cost visibility  
- Resource utilization analytics  

### **DevSecOps**
- Trivy scanning for:
  - Docker images  
  - Terraform IaC  
  - K8s manifests  
  - Helm charts  

---

# Project Structure
```
express-t2s-app-v6/
├── app/
├── aiops-service/
├── charts/
│   ├── express-web-app/
│   ├── aiops/
│   ├── grafana/
│   └── prometheus/
├── argocd/
├── scripts/
│   ├── cleanup.sh
│   ├── finops-test.sh
│   ├── force_destroy.sh
│   ├── generate-traffic.sh
│   ├── port-forward-aiops.sh
│   └── trivy-scan.sh
├── terraform/
│   ├── backend/
│   ├── ecr/
│   └── eks/
└── README.md
```

---

# Architecture Diagram
```
                   GitHub (Source of Truth)
                            │
                            ▼
                       ArgoCD GitOps
                  (Auto Sync + Drift Fix)
                            │
                            ▼
     ┌────────────────────────────────────────────┐
     │                Amazon EKS                  │
     └────────────────────────────────────────────┘
         │                   │                 │
         ▼                   ▼                 ▼
   Express App            AIOps        Prometheus/Grafana
         │                   │                 │
         ▼                   ▼                 ▼
   AWS ALB Ingress       Alerts        Dashboards / SLIs/SLOs
```

---

# Real Companies Using This Architecture

| Company      | Technology Alignment |
|--------------|----------------------|
| Netflix      | Kubernetes, ArgoCD, Prometheus, Terraform |
| Riot Games   | Global K8s + Observability |
| Epic Games   | Autoscaling infra for Fortnite |
| Disney+      | EKS + Terraform IaC |
| Roblox       | High-scale multi-region Kubernetes |
| Shopify      | Kubernetes + FinOps cost management |
| Coinbase     | Terraform + K8s + High Security |

Your system now reflects the same world‑class patterns.

---

# Deployment Guide — Full Steps

---

## **STEP 1 — Provision Terraform Backend**
```bash
cd terraform/backend
terraform init
terraform apply -auto-approve
```

---

## **STEP 2 — Build & Push Image to ECR**
```bash
cd terraform/ecr
terraform init && terraform apply -auto-approve
chmod +x build_and_push.sh
bash build_and_push.sh
```

---

## **STEP 3 — Provision the EKS Cluster**
```bash
cd terraform/eks
terraform init
terraform apply -auto-approve
```

---

## **STEP 4 — Configure kubectl**
```bash
aws eks update-kubeconfig --region us-east-1 --name t2s-eks
kubectl get nodes
```

---

## **STEP 5 — Deploy Express App Using Helm**
- Before deploying the App, we will first install kube-prometheus-stack first so that we also auto-install all CRDs. 
```bash
cd ../..

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace
```
- Now, let's deploy the Express App:
```bash
helm upgrade --install express-web-app ./charts/express-web-app   -n apps --create-namespace
```

---

# Monitoring Stack — Prometheus & Grafana

## **Install kube-prometheus-stack**
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack   -n monitoring --create-namespace
```

## **Install Custom Grafana Chart**
```bash
helm upgrade --install grafana ./charts/grafana -n monitoring
```

## **Get Grafana Password**
```bash
kubectl --namespace monitoring get secrets kube-prometheus-stack-grafana   -o jsonpath="{.data.admin-password}" | base64 -d
```

## **Port‑forward Grafana**
```bash
kubectl --namespace monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80
```

## **Create a custom Grafana Dashboard**
- 

---

# Deploy AIOps Engine

- Build, tag and push the AIOps image to ECR
```bash
chmod +x scripts/build_and_push_aiops.sh
bash scripts/build_and_push_aiops.sh
```
- Deploy the AIOps App
```bash
helm upgrade --install aiops ./charts/aiops -n aiops --create-namespace
```
- Port-forward dashboard:
```bash
bash scripts/port-forward-aiops.sh
```

Simulate high traffic:
```bash
bash scripts/generate-traffic.sh
```

Expected outcomes:
- Latency spikes detected  
- Error-rate anomalies logged  
- Alerts generated  
- Prometheus metrics updated  

---

# Deploy ArgoCD (GitOps)
```bash
kubectl create namespace argocd
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

helm upgrade --install argocd argo/argo-cd   -n argocd --set server.service.type=ClusterIP
```

### **Deploy GitOps App**
```bash
kubectl apply -f argocd/express-web-app.yaml
```

### **Access ArgoCD over the Browser**
```bash
kubectl --namespace argocd port-forward svc/argocd-server 8080:443
```

### **Get Admin Password**
```bash
kubectl -n argocd get secret argocd-initial-admin-secret   -o jsonpath="{.data.password}" | base64 -d
```

ArgoCD now:
- Auto-syncs deployments  
- Corrects drift  
- Provides rollbacks  
- Enforces GitOps source-of-truth  

---

# Testing AIOps, FinOps & DevSecOps

---

## **AIOps Validation**
Simulate workloads:
```bash
bash scripts/generate-traffic.sh
```
Observe AIOps dashboard:
```bash
bash scripts/port-forward-aiops.sh
```

---

## **FinOps Validation**
```bash
bash scripts/finops-test.sh
```

Output includes:
- CPU/memory overprovisioning  
- Cost anomaly alerts  
- Pod cost estimation  

---

## **DevSecOps Validation**
```bash
bash scripts/trivy-scan.sh
```

Scans:
- Docker images  
- Terraform modules  
- Kubernetes manifests  
- Helm charts  

---

## 7. Root-level `README.md` (Full Case Study)

Here is a **complete root README** you can use to replace or upgrade your existing one.

```md
# Express Web App – Version 7  
## SRE Consultancy Edition for Fortune 500 & FAANG-Scale Systems

This repository combines a production-style Express application with cloud-native infrastructure and a full SRE toolkit. Version 7 is designed as a **case study** of how a modern Fortune 500 or FAANG company can:

- Ship features quickly.
- Maintain high reliability.
- Reduce incident impact.
- Introduce AIOps and automation.
- Align engineering with business outcomes through SLOs.

It is built to function both as:
- A working reference implementation.
- An SRE consulting and training artifact.

---

## 1. Business Problem This Repo Solves

Large organizations typically struggle with:

- **Fragmented reliability practices:** Every team has different dashboards, alert thresholds, and deployment workflows.
- **Reactive firefighting:** Incidents are discovered by customers or executives before observability tools.
- **Alert noise:** Thousands of low-value alerts with no clear tie to user experience.
- **Manual runbooks:** No automation for common incident patterns.
- **No continuous validation:** DR plans and failover designs are rarely tested.
- **Limited AIOps:** Capacity and reliability decisions are still manual and anecdotal.

This repo demonstrates how to address these issues using a **cohesive SRE operating model** integrated into a real application stack.

---

## 2. High-Level Architecture

Core components:

- **App:** Express-based web service and frontend under `app/`.
- **Platform:** Kubernetes (EKS or equivalent) with manifests in `k8s/` and `charts/`.
- **Infrastructure:** Terraform modules and scripts in `infra/` for:
  - EKS cluster provisioning.
  - ECR repositories.
  - Networking and IAM.
- **GitOps / CI/CD:** GitHub Actions and ArgoCD-based workflows under `scripts/` and `argocd/`.
- **SRE Toolkit:** Scripts and playbooks under `sre/` for:
  - Chaos engineering.
  - Observability.
  - SLO/error-budget enforcement.
  - Incident simulation.
  - AIOps forecasting and anomaly detection.
  - Security and RBAC governance.

---

## 3. SRE Toolkit Overview (`sre/`)

The `sre/` folder is the heart of the Version 7 consultancy layer.

### 3.1 AIOps (`sre/aiops`)

Python utilities to:
- Detect anomalies in metrics.
- Forecast usage or demand (e.g., traffic, CPU).
- Recommend autoscaling changes.
- Cluster logs into patterns to reduce alert noise.

These can be wired into:
- CI/CD quality checks.
- Capacity planning sessions.
- Continuous reliability reviews.

### 3.2 Chaos Engineering (`sre/chaos`)

Shell scripts to:
- Kill pods and drain nodes.
- Inject network latency or packet loss.
- Simulate dependency failures.
- Test region failover via DNS or traffic routing.

These scripts let you **prove** resilience rather than just believing in diagrams.

### 3.3 Observability (`sre/observability`)

Scripts and docs to:
- Install Datadog agents.
- Configure synthetic tests.
- Enable OpenTelemetry collectors.
- Design log correlation between traces and logs.

This is the observability standard you can apply across multiple teams.

### 3.4 Reliability Governance (`sre/reliability`)

Tools and docs to:
- Define SLOs and SLIs.
- Check SLO burn rates via API.
- Simulate error-budget consumption.
- Create practice incidents and run through scenario playbooks.
- Describe the reliability architecture and how it maps to business goals.

This is what you take into leadership discussions to align reliability with strategy.

### 3.5 Security and Access (`sre/security`)

Okta-based scripts and docs to:
- Enforce MFA for production access.
- Automate SCIM provisioning.
- Define RBAC for SRE roles in Kubernetes.
- Document SSO integration options.

This helps move from “trust by default” to **least-privilege, identity-centric** operations.

---

## 4. How Fortune 500 / FAANG Teams Can Use This

### 4.1 As a Reference Implementation

Architecture, scripts, and SRE workflows here can be adapted into:
- Centralized SRE platforms.
- Internal golden paths for teams.
- Training material for new engineers.

### 4.2 As a Consulting Blueprint

For SRE / DevOps consultants:
- Use the repo to demonstrate your approach to reliability.
- Map a client’s environment to this structure (gap analysis).
- Propose phased adoption: observability → SLOs → chaos → AIOps.

### 4.3 As an Internal Enablement Kit

Engineering orgs can:
- Run internal workshops around the `sre/` scripts.
- Use `sre/reliability` as a pattern for defining SLOs.
- Integrate `sre/chaos` tests into staging environments.
- Leverage `sre/aiops` for forecasting and anomaly detection prototypes.

---

## 5. Getting Started

### Prerequisites

- Node.js and npm.
- Docker.
- Access to a Kubernetes cluster (EKS recommended).
- Terraform CLI if you are provisioning infra.
- (Optional) Datadog account + API keys.
- (Optional) Okta tenant for SSO/MFA demos.

### 5.1 Run App Locally

```bash
cd app
npm install
npm start

---

# Cleanup (Safe VPC + EKS Teardown)
```bash
kubectl delete deployment aiops-api -n aiops
kubectl delete service aiops-api -n aiops
kubectl delete configmap aiops-api-config -n aiops --ignore-not-found
kubectl delete serviceaccount aiops-sa -n aiops --ignore-not-found
kubectl delete pod -l app=aiops-api -n aiops --ignore-not-found

chmod +x scripts/cleanup.sh
export FORCE_TERMINATE_INSTANCES=true
AWS_REGION=us-east-1 VPC_ID=<your-vpc-id> bash scripts/cleanup.sh

cd /terraform/eks
terraform destroy -auto-approve

cd ../..
export FORCE_TERMINATE_INSTANCES=true
AWS_REGION=us-east-1 VPC_ID=<your-vpc-id> bash scripts/cleanup.sh

cd terraform/ecr
aws ecr batch-delete-image \
  --repository-name t2s-express-app \
  --image-ids imageTag=latest
aws ecr batch-delete-image \
  --repository-name aiops-api \
  --image-ids imageTag=latest
terraform destroy -auto-approve

cd ../..
export FORCE_TERMINATE_INSTANCES=true
AWS_REGION=us-east-1 VPC_ID=<your-vpc-id> bash scripts/cleanup.sh

terraform destroy -auto-approve
```

Destroys:
- EKS cluster  
- Node groups  
- Load balancers  
- NAT GWs  
- Subnets  
- SGs, NACLs, RTs  
- VPC  

---

# Final Outcome
This modernization delivers:

✔ Enterprise-grade resiliency  
✔ Autoscaling Kubernetes platform  
✔ GitOps automated workflows  
✔ Production-grade monitoring (SLIs/SLOs)  
✔ AIOps anomaly detection  
✔ FinOps cost governance  
✔ Zero‑downtime deployments  
✔ Secure DevSecOps pipelines  

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

