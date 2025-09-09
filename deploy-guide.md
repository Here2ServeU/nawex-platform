# Beginner2Mastery — Express Web App → EKS with ALB (Dev-Ready, Prod-Style)

This guide matches **your current repo layout** and uses the included scripts so you can go from zero → running quickly.

```
app/
  Dockerfile
  index.js
  package.json
  public/index.html
deploy-guide.md
k8s/
  deployment.yaml
  ingress.yaml
  namespace.yaml
  service.yaml
scripts/
  deploy_app.sh
  get_url.sh
  install_helm.sh
  provision.sh
  cleanup-igw.sh
terraform/
  backend/
    main.tf
    outputs.tf
    terraform.tfstate
    terraform.tfvars
    variables.tf
  ecr/
    backend.tf
    build_and_push.sh
    main.tf
    outputs.tf
    terraform.tfvars
    variables.tf
  eks/
    main.tf
    policies/aws-load-balancer-controller.json
    variables.tf
    versions.tf
```

---

## 0) Prereqs
- **CLI tools:** `aws`, `kubectl`, `terraform >= 1.3`, `helm`, `docker`, `jq`, `git`
- **AWS access:** Ability to create IAM, VPC, EKS, ECR, ALB
- **Region:** defaults to `us-east-1` (make sure your ECR/EKS/ALB are all in the same region)

> If you haven’t installed Helm on this machine yet:
```bash
bash scripts/install_helm.sh
```

---

## 1) Remote State (Terraform Backend)
**Folder:** `terraform/backend`  
This stack provisions (or references) the S3 bucket + DynamoDB table that your other Terraform stacks use.

```bash
cd terraform/backend
terraform init
terraform apply -auto-approve
```

> If your `terraform/ecr` and `terraform/eks` already have `backend` blocks (they do), make sure their values match your S3 bucket, table, and region.

---

## 2) ECR Repository + Build & Push the Image
**Folder:** `terraform/ecr`

1) **Create/ensure ECR repo**
```bash
cd ../../terraform/ecr
terraform init
terraform apply -auto-approve
# Outputs include the repository URL
```

2) **Build & Push** (uses `app/` Dockerfile)  
The repo includes a helper: `build_and_push.sh`.

```bash
# from terraform/ecr
bash build_and_push.sh
# Copy the IMAGE_URI printed at the end, like:
#  <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/express-web-app:<GIT_SHA>
```

---

## 3) Provision the EKS Cluster + ALB Controller
**Script:** `scripts/provision.sh`

```bash
cd ../../..   # back to repo root
bash scripts/provision.sh

# Sanity checks
kubectl get nodes
kubectl -n kube-system get deploy aws-load-balancer-controller
```

What this creates:
- **VPC** with public/private subnets + NAT
- **EKS** (1.29), managed node group
- **IRSA** with least-privileged IAM for the ALB controller
- ALB controller installed via **Helm**

---

## 4) Deploy the App behind ALB
**Script:** `scripts/deploy_app.sh`

```bash
# 1) Set IMAGE_URI from the ECR build step
export IMAGE_URI=<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/express-web-app:<GIT_SHA>

# 2) Deploy
bash scripts/deploy_app.sh

# 3) Get the ALB URL
bash scripts/get_url.sh
# → prints an http://<alb-dns>/ address
```

> Health endpoint: the deployment uses `readinessProbe` on `/health` (port 3000). Make sure your `app/index.js` serves it.

---

## 5) (Optional) HTTPS with ACM
See the example `k8s/ingress-tls.yaml` in this guide for HTTPS with ACM.

---

## 6) Day-2 Add-Ons (optional)
- **cert-manager** for TLS automation  
- **Kyverno** for policy enforcement  
- **Falco** for runtime security  
- **Kubecost** for cost visibility  

---

## 7) CI/CD (optional)
Use GitHub Actions → build, scan, push to ECR → update K8s deployment via GitHub OIDC.

---

## 8) Troubleshooting
- **Ingress has no ADDRESS** → ALB controller not ready, or subnet tags missing.  
- **502/503** → check readinessProbe, service targetPort, and logs.  
- **ImagePullBackOff** → ECR image/tag mismatch or IAM issue.  

---

## 9) Cleanup

1. Remove the app:
```bash
kubectl delete ns apps --ignore-not-found
```

2. Destroy infra (reverse order):
```bash
cd terraform/eks  && terraform destroy -auto-approve
cd ../ecr         && terraform destroy -auto-approve
# usually keep terraform/backend state infra
```

3. If Terraform fails with **DependencyViolation** errors (common with ALBs, ENIs, IGWs), run the helper:

```bash
bash scripts/cleanup-igw.sh
```

This script:
- Deletes leftover **ALBs/NLBs** and target groups  
- Removes orphaned ENIs created by ELB/NLB  
- Releases NAT EIPs  
- Disables public IP auto-assign on subnets  
- Detaches & deletes the **Internet Gateway**

After that, re-run:

```bash
cd terraform/eks
terraform destroy -auto-approve
```

---

With this flow you can go **Dockerfile → ECR → EKS → ALB → cleanup** fully using the repo scripts.  

---

## Author

By Emmanuel Naweji, 2025  
**Cloud | DevOps | SRE | FinOps | AI Engineer**  
Helping businesses modernize infrastructure and guiding engineers into top 1% career paths through real-world projects and automation-first thinking.

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
