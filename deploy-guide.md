# Beginner2Mastery — Express Web App on EKS (Production‑grade in Dev)  
**Project layout**
```
app/
deploy-guide.md
k8s/
terraform/
  backend/
  ecr/
  eks/
.github/
  workflows/
    deploy.yml
```

This guide takes you from empty AWS resources to: **EKS + ALB (HTTPS via ACM), GitHub OIDC CI/CD, and SRE/FinOps/DevSecOps add‑ons (Kyverno, Falco, Kubecost)**. It’s structured for **dev first** with **production‑grade defaults** (IRSA, policies, scanning).

---

## 0) Prereqs
- **AWS** account with permissions to create IAM, VPC, EKS, ECR, ACM, Route53 (optional for LE).
- **CLIs**: `aws`, `kubectl`, `helm`, `terraform >= 1.3`, `docker`, `jq`, `git`.
- **S3 + DynamoDB** for Terraform state (created below).  
- **Domain** (for HTTPS via ACM). Use a real domain in **us-east-1** (N. Virginia) for ALB TLS.

> Region defaults to `us-east-1`. Replace as needed (keep ACM + ALB in the same region).

---

## 1) Remote Terraform Backend (S3 + DynamoDB)
**Folder:** `terraform/backend`

Create an S3 bucket (versioned, encrypted, TLS‑only) and a DynamoDB table for state locking.

```bash
cd terraform/backend
terraform init
terraform apply -auto-approve
# Outputs: backend_bucket, lock_table
```

Create a `backend.hcl` in each Terraform subproject you plan to migrate (or hardcode the backend in `terraform { backend "s3" { ... } }`). Example:
```hcl
bucket         = "emmanuel-tf-state-09042025"
key            = "eks/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-locks"
encrypt        = true
```

> If you hardcode the backend in Terraform (recommended here), ensure the values match your bucket/table.

---

## 2) ECR Repository (secure image registry)
**Folder:** `terraform/ecr`

Create an ECR repository with scan‑on‑push and encryption.

```bash
cd terraform/ecr
terraform init
terraform apply -auto-approve
# Note the `repository_url` output
```

> Alternatively, one‑liner:  
> `aws ecr create-repository --repository-name express-web-app --region us-east-1`

---

## 3) EKS Cluster + ALB Controller + Add‑ons (Terraform)
**Folder:** `terraform/eks`

This stack provisions:
- **VPC** (public/private subnets, NAT, correct ELB subnet tags)
- **EKS** (v1.29 by default), **IRSA**, managed node group (t3.medium x2)
- **AWS Load Balancer Controller (ALB)** via **Helm** with **IRSA**
- Optional **NGINX Ingress** (internet‑facing LB) — off by default unless enabled
- **cert‑manager**, **Kyverno** (+ baseline policies), **Falco**, **Kubecost**
- **GitHub OIDC deploy role** + EKS access so CI/CD can `kubectl` safely

> Ensure your Terraform backend block is set to your S3 + DynamoDB (e.g., in `versions.tf`). Example:
```hcl
terraform {
  backend "s3" {
    bucket         = "emmanuel-tf-state-09042025"
    key            = "eks/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
```

**Configure repo identity for CI/CD role mapping** (edit variables or TF vars):
```hcl
# in terraform/eks/main.tf (or variables.tf via -var):
github_org  = "YOUR_GITHUB_USER_OR_ORG"
github_repo = "YOUR_REPO_NAME"
```

**Apply:**
```bash
cd terraform/eks
terraform init
terraform apply -auto-approve

# Kubeconfig
aws eks update-kubeconfig   --name   $(terraform output -raw cluster_name)   --region $(terraform output -raw region)

# Sanity checks
kubectl get nodes
kubectl -n kube-system get deploy aws-load-balancer-controller
```

> Subnets must be tagged (this stack does it) so that ALB can attach to public subnets.

---

## 4) Build & Push the Express Image
**Folder:** `app` (must contain Dockerfile)

```bash
cd app
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO=express-web-app

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build & tag
docker build -t $ECR_REPO:latest .
IMAGE_TAG=$(git rev-parse --short HEAD || date +%s)
docker tag $ECR_REPO:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG

# Push
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG

# Capture for deployment
export IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"
echo $IMAGE_URI
```

---

## 5) Deploy Manifests (ALB Ingress)
**Folder:** `k8s`

**Files you have:**
- `namespace.yaml`
- `deployment.yaml` (uses `REPLACE_WITH_IMAGE_URI`)
- `service.yaml`
- `ingress.yaml` (HTTP)
- `ingress-tls.yaml` (HTTPS via ACM)

Update the deployment to your image and apply:
```bash
cd k8s
sed -i.bak "s|REPLACE_WITH_IMAGE_URI|$IMAGE_URI|g" deployment.yaml

kubectl apply -f namespace.yaml
kubectl -n apps apply -f deployment.yaml -f service.yaml -f ingress.yaml

# Get public DNS (ALB)
kubectl -n apps get ingress express-web -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'; echo
```

**Health check:**
```bash
curl http://$(kubectl -n apps get ingress express-web -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')/health
```

---

## 6) HTTPS with ACM on the ALB
**ACM certificate (us-east-1)**: request a public cert for your domain/subdomain and validate it.  
Edit `k8s/ingress-tls.yaml` and set your **certificate ARN**:
```yaml
annotations:
  kubernetes.io/ingress.class: alb
  alb.ingress.kubernetes.io/scheme: internet-facing
  alb.ingress.kubernetes.io/target-type: ip
  alb.ingress.kubernetes.io/listen-ports: '[{"HTTP":80,"HTTPS":443}]'
  alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:<acct>:certificate/<CERT-ID>
  alb.ingress.kubernetes.io/ssl-redirect: '443'
```
Apply:
```bash
kubectl -n apps apply -f ingress-tls.yaml
kubectl -n apps get ingress express-web-tls -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'; echo
# Test:
curl -I https://<ALB-DNS>/
```

> **cert-manager** is installed for future **Let’s Encrypt** automation (Route53 DNS‑01). If you want that now, create a `ClusterIssuer` and change your ingress to reference a cert-manager `Certificate` instead of ACM.

---

## 7) SRE/FinOps/DevSecOps Add‑ons (via Terraform Helm releases)
Already installed by `terraform/eks`:

- **Kyverno** (policy): baseline rules to **disallow `:latest`** and **require resources**.  
  Check:
  ```bash
  kubectl -n kyverno get deploy,policies,policyreport --all-namespaces
  ```

- **Falco** (runtime security): detects suspicious syscalls/processes.  
  Check events:
  ```bash
  kubectl -n falco get pods
  kubectl -n falco logs deploy/falco | head
  ```

- **Kubecost** (FinOps): quick visibility into cluster spend.  
  Access (port‑forward for now):
  ```bash
  kubectl -n kubecost port-forward svc/kubecost-cost-analyzer 9090:9090
  # open http://localhost:9090
  ```

---

## 8) CI/CD with GitHub Actions (OIDC, no static keys)
**Terraform role & RBAC**:  
In `terraform/eks`, set:
```hcl
github_org  = "YOUR_GITHUB_USER_OR_ORG"
github_repo = "YOUR_REPO_NAME"
```
Then:
```bash
cd terraform/eks
terraform apply -auto-approve
# Output: gh_actions_role_arn
```

**GitHub repo secrets (Settings → Secrets and variables → Actions):**
- `AWS_GH_ROLE_ARN` → value from `gh_actions_role_arn`
- `ECR_REPO` → `express-web-app` (or your repo name)
- `EKS_CLUSTER` → Terraform output `cluster_name`
- `EKS_REGION` → `us-east-1`
- `K8S_NAMESPACE` → `apps`

**Workflow file:** `.github/workflows/deploy.yml`
- On push to `main`: **build → Trivy scan → push to ECR → deploy to EKS**.
- Requires `Dockerfile` at repo root or adjust the `docker build` path.

_Pseudocode of stages (actual file is in the repo):_
```
- configure-aws-credentials (OIDC role)
- login to ECR
- docker build, tag -> ${{ github.sha }}
- trivy scan image
- docker push
- aws eks update-kubeconfig
- sed image into k8s/deployment.yaml
- kubectl apply namespace,deployment,service
- apply ingress-tls.yaml if ACM ARN present, else ingress.yaml
- wait for rollout
```

> This mirrors what FAANG/F500 CI systems do: assume a **short‑lived role**, scan artifacts, push to a private registry, then **declaratively update** Kubernetes.

---

## 9) Operations & Hardening Quick Wins
- **Autoscaling**: `kubectl -n apps autoscale deploy express-web --cpu-percent=60 --min=2 --max=6`
- **PDB**: add a PodDisruptionBudget for zero‑downtime during maintenance.
- **Secrets**: migrate app secrets to **AWS Secrets Manager** + **CSI Driver**.
- **WAF & Shield**: attach AWS WAFv2 to ALB, enable Shield Advanced if applicable.
- **Logging**: send ALB access logs to S3; enable **Container Insights**/OTEL.
- **Backup**: EBS snapshot policies or Velero for cluster objects and volumes.
- **Network**: baseline **NetworkPolicies** (default‑deny + egress allowlist).

---

## 10) Troubleshooting
- **Ingress has no ADDRESS** → verify ALB controller is running; subnets have ELB tags; nodes have internet; security groups allow egress.
- **502/503 from ALB** → check readiness probe path/port; service targetPort; pod logs: `kubectl -n apps logs deploy/express-web -f`.
- **ImagePullBackOff** → wrong image URI or permissions. Nodes can pull from ECR by default; verify repo region/URI/tag.
- **Kyverno blocks deploy** → fix policies (no `:latest`, add requests/limits).
- **CD permission denied** → confirm `AWS_GH_ROLE_ARN` and EKS access entry; re‑`terraform apply` after changing `github_org/repo`.
- **State lock stuck** → release lock in DynamoDB **carefully** (only if no terraform is running).

---

## 11) Cleanup
Destroy in reverse order (app → eks → ecr → backend if desired):
```bash
# Delete app resources
kubectl delete ns apps --ignore-not-found

# Terraform destroys
cd terraform/eks  && terraform destroy -auto-approve
cd ../ecr         && terraform destroy -auto-approve
# (Usually keep backend S3/DynamoDB for future runs)
```

---

## Appendix — Reference Manifests (k8s/)
**k8s/namespace.yaml**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: apps
```

**k8s/deployment.yaml**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: express-web
  namespace: apps
  labels:
    app: express-web
spec:
  replicas: 2
  selector:
    matchLabels:
      app: express-web
  template:
    metadata:
      labels:
        app: express-web
    spec:
      containers:
        - name: app
          image: REPLACE_WITH_IMAGE_URI
          ports:
            - containerPort: 3000
          env:
            - name: PORT
              value: "3000"
          readinessProbe:
            httpGet:
              path: /health
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 5
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
```

**k8s/service.yaml**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: express-web-svc
  namespace: apps
spec:
  type: ClusterIP
  selector:
    app: express-web
  ports:
    - port: 80
      targetPort: 3000
```

**k8s/ingress.yaml (HTTP)**  
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: express-web
  namespace: apps
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
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

**k8s/ingress-tls.yaml (HTTPS via ACM)**
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

---

## Appendix — GitHub Actions Workflow
**.github/workflows/deploy.yml**
```yaml
name: CI-CD to EKS (ECR + OIDC)

on:
  push:
    branches: [ "main" ]

permissions:
  id-token: write
  contents: read

env:
  AWS_REGION: ${{ secrets.EKS_REGION }}
  EKS_CLUSTER: ${{ secrets.EKS_CLUSTER }}
  K8S_NAMESPACE: ${{ secrets.K8S_NAMESPACE }}
  ECR_REPO: ${{ secrets.ECR_REPO }}

jobs:
  build_scan_push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_GH_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build image
        run: |
          docker build -t $ECR_REPO:latest .
          IMAGE_URI=${{ steps.login-ecr.outputs.registry }}/${ECR_REPO}:${{ github.sha }}
          echo "IMAGE_URI=$IMAGE_URI" >> $GITHUB_ENV

      - name: Trivy scan
        uses: aquasecurity/trivy-action@0.28.0
        with:
          image-ref: ${{ env.IMAGE_URI }}
          format: 'table'
          ignore-unfixed: true
          vuln-type: 'os,library'
          severity: 'CRITICAL,HIGH,MEDIUM,LOW'

      - name: Push image
        run: docker push $IMAGE_URI

  deploy:
    needs: build_scan_push
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_GH_ROLE_ARN }}
          aws-region: ${{ secrets.EKS_REGION }}

      - name: Setup kubectl
        uses: azure/setup-kubectl@v4

      - name: Update kubeconfig
        run: aws eks update-kubeconfig --name "$EKS_CLUSTER" --region "$AWS_REGION"

      - name: Set image in manifest
        run: |
          sed -i 's|REPLACE_WITH_IMAGE_URI|'"$IMAGE_URI"'|g' k8s/deployment.yaml

      - name: Apply namespace + manifests
        run: |
          kubectl apply -f k8s/namespace.yaml
          kubectl -n "$K8S_NAMESPACE" apply -f k8s/deployment.yaml -f k8s/service.yaml
          if grep -q 'certificate-arn' k8s/ingress-tls.yaml; then
            kubectl -n "$K8S_NAMESPACE" apply -f k8s/ingress-tls.yaml
          else
            kubectl -n "$K8S_NAMESPACE" apply -f k8s/ingress.yaml
          fi
          kubectl -n "$K8S_NAMESPACE" rollout status deploy/express-web
```

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

