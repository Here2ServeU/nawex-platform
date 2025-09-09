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
# Note outputs (bucket + lock table) if you need them elsewhere
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
The repo includes a helper: `build_and_push.sh`. It logs in to ECR, builds the image, tags with the current git SHA, and pushes.

```bash
# from terraform/ecr
bash build_and_push.sh
# Copy the IMAGE_URI printed at the end, it will look like:
#  <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/express-web-app:<GIT_SHA>
```

> If you prefer manual steps instead of the script, build/push from `app/` using the standard ECR login → build → tag → push flow.

---

## 3) Provision the EKS Cluster + ALB Controller
**Script:** `scripts/provision.sh`  
This calls into `terraform/eks`, applies the VPC + EKS + IRSA + **AWS Load Balancer Controller (ALB)**, then updates your kubeconfig.

```bash
cd ../../..   # go back to repo root
bash scripts/provision.sh

# Sanity checks
kubectl get nodes
kubectl -n kube-system get deploy aws-load-balancer-controller
```

What this creates:
- **VPC** with public/private subnets + NAT
- **EKS** (1.29), managed node group
- **IRSA** with least‑privileged IAM for the ALB controller
- ALB controller installed via **Helm** (so `Ingress` → public ALB works)

---

## 4) Deploy the App behind ALB
**Script:** `scripts/deploy_app.sh`  
- Uses your k8s manifests in `k8s/`
- Replaces `REPLACE_WITH_IMAGE_URI` in `deployment.yaml` using env var `IMAGE_URI`
- Applies namespace, deployment, service, and ingress

```bash
# 1) Set the IMAGE_URI you copied from the ECR build step
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
Right now `k8s/ingress.yaml` exposes **HTTP**. When you’re ready for **HTTPS**:
1. Request/validate an **ACM** certificate in the same region (e.g., `us-east-1`) for your domain or subdomain.
2. Create a `k8s/ingress-tls.yaml` like this and apply it instead of `ingress.yaml`:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: express-web-tls
  namespace: apps
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP":80,"HTTPS":443}]'
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:<acct>:certificate/<CERT-ID>
    alb.ingress.kubernetes.io/ssl-redirect: '443'
spec:
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: express-web-svc
            port:
              number: 80
```
```bash
kubectl -n apps apply -f k8s/ingress-tls.yaml
```

---

## 6) Day‑2 Add‑Ons (optional)
- **cert-manager**: for Let’s Encrypt automation (Route 53 DNS‑01).  
- **Kyverno**: enforce policies (no `:latest`, require requests/limits).  
- **Falco**: runtime threat detection.  
- **Kubecost**: FinOps visibility.  

> If you want, I’ll add a `terraform/eks-addons` submodule that installs these with Helm and sensible defaults.

---

## 7) CI/CD (optional)
- Use **GitHub OIDC** (no static keys) → build, **Trivy** scan, push to ECR → update K8s deployment.
- I can drop a `.github/workflows/deploy.yml` that works with this layout and your Terraform IAM role for GitHub.

---

## 8) Troubleshooting
- **Ingress has no ADDRESS** → ALB controller not ready, or subnet tags missing. Check:
  ```bash
  kubectl -n kube-system get deploy aws-load-balancer-controller
  ```
- **502/503** → check the app `readinessProbe`, service `targetPort`, and logs:
  ```bash
  kubectl -n apps logs deploy/express-web -f
  ```
- **ImagePullBackOff** → ECR image/tag mismatch, region mismatch, or role/node permissions.

---

## 9) Cleanup
```bash
# Remove app
kubectl delete ns apps --ignore-not-found

# Destroy infra (in reverse)
cd terraform/eks  && terraform destroy -auto-approve
cd ../ecr         && terraform destroy -auto-approve
# (usually keep terraform/backend state infra for future runs)
```

---

## Quick Commands (copy/paste)

```bash
# Prereqs
bash scripts/install_helm.sh

# Backend
cd terraform/backend
terraform init && terraform apply -auto-approve

# ECR + build/push
cd ../ecr
terraform init && terraform apply -auto-approve
bash build_and_push.sh
# Copy IMAGE_URI printed at the end

# EKS (provisions VPC/EKS + ALB controller + kubeconfig)
cd ../../
bash scripts/provision.sh

# Deploy app
export IMAGE_URI=<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/express-web-app:<GIT_SHA>
bash scripts/deploy_app.sh
bash scripts/get_url.sh
```

That’s it—fastest path from **Dockerfile → ECR → EKS → ALB** using your repo as‑is. If you’d like, I’ll also generate the TLS `ingress-tls.yaml` and a working GitHub Actions pipeline wired to your IAM role.

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

---

## Connect with Me

- [LinkedIn](https://www.linkedin.com/in/ready2assist/)
- [GitHub](https://github.com/Here2ServeU)
- [Medium](https://medium.com/@here2serveyou)

---

## Book a Free Consultation

Let’s talk about modernizing your cloud infrastructure or DevOps strategy.  
👉🏾 [Schedule a free 1:1 consultation](https://bit.ly/letus-meet)

