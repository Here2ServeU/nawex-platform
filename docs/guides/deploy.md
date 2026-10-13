# Deploying to AWS, Azure, GCP or OpenShift

The platform deploys in two layers:

1. **Landing zone** — Terraform in `deploy/terraform/live/<cloud>/<env>`: Kubernetes cluster, container registry,
   optional GPU node pool, and a workload identity for the platform's service account.
2. **Platform** — Helm chart `deploy/helm/golden` with the cloud overlay `values-<cloud>.yaml`.

`scripts/deploy.sh <cloud> <env> <plan|apply|destroy>` runs both. `make plan` / `make deploy` / `make destroy`
call it with `CLOUD`/`ENV` from `platform.yaml`. `scripts/deploy.sh ... --dry-run` prints every command without
executing anything.

## Every landing zone has the same interface

| Input | Meaning |
| --- | --- |
| `project` | name prefix for every resource (default `golden`) |
| `environment` | `dev` · `staging` · `prod` |
| `region` | cloud region |
| `kubernetes_version`, `node_count`, `node_instance_type` | system node pool |
| `gpu_node_pool_enabled`, `gpu_instance_type`, `gpu_node_count` | optional GPU pool, tainted `nvidia.com/gpu=present:NoSchedule` |

| Output | Used by |
| --- | --- |
| `cluster_name`, `cluster_endpoint` | humans / CI summary |
| `registry_url` | `helm --set image.registry=…` |
| `kubeconfig_command` | `deploy.sh` runs it to get cluster credentials |
| `workload_identity` | annotated onto the platform service account |

Copy `terraform.tfvars.example` → `terraform.tfvars` and `backend.hcl.example` → `backend.hcl` in the environment
directory (both git-ignored) to customise values and use remote state.

## Local workstation

```bash
make doctor                       # terraform, helm, kubectl, cloud CLI present?
aws sso login        # or: az login   /   gcloud auth application-default login
make plan  CLOUD=aws ENV=dev
make deploy CLOUD=aws ENV=dev     # builds nothing locally; uses images from the registry (TAG=<sha>)
```

`local` uses kind and `values-local.yaml`. `openshift` skips Terraform and uses your current `oc` login.

## GitHub Actions (keyless OIDC)

The `deploy` workflow (manual dispatch: *cloud*, *environment*, *action*, *image_tag*) authenticates with
short-lived OIDC tokens. Create GitHub **Environments** `dev`, `staging`, `prod` (add required reviewers to staging
and prod) and set the variables below on the repository or environment.

### AWS
1. Create the IAM OIDC provider `token.actions.githubusercontent.com` (audience `sts.amazonaws.com`).
2. Create a deploy role whose trust policy allows
   `repo:<owner>/<repo>:environment:<env>` on `token.actions.githubusercontent.com:sub`.
   Grant it what the landing zone needs (EKS, ECR, VPC, IAM for IRSA), scoped per environment.
3. Variables: `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`.

### Azure
1. Create an app registration (or user-assigned managed identity) and add a **federated credential** with issuer
   `https://token.actions.githubusercontent.com` and subject `repo:<owner>/<repo>:environment:<env>`.
2. Grant it Contributor (+ User Access Administrator if Terraform creates role assignments) on the target
   subscription/resource group.
3. Variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.

### GCP
1. Create a Workload Identity Pool + OIDC provider for `https://token.actions.githubusercontent.com` with attribute
   condition `assertion.repository == "<owner>/<repo>"`.
2. Allow it to impersonate a deploy service account (`roles/iam.workloadIdentityUser`); grant that account
   GKE, Artifact Registry and network admin roles on the project.
3. Variables: `GCP_WORKLOAD_IDENTITY_PROVIDER` (full resource name), `GCP_SERVICE_ACCOUNT`, `GCP_PROJECT_ID`.

### OpenShift (self-managed, ROSA, ARO)
Secrets: `OPENSHIFT_SERVER`, `OPENSHIFT_TOKEN` (a service-account token with rights in the target namespace).

### Remote state
Store the contents of `backend.hcl` as the environment secret `TF_BACKEND_CONFIG`. Without it the workflow uses
local state and warns — acceptable only for throwaway `dev` runs.

## After deploying

```bash
kubectl -n golden get pods
kubectl -n golden port-forward svc/golden-api 8000:8000 && open http://localhost:8000/docs
golden security status          # autonomy mode, kill switch, caps (also GET /v1/security/status)
```

Promote autonomy deliberately: `dry_run` → `supervised` → `autonomous`, per environment, via
`ai_safety.autonomy_mode` in `platform.yaml` (rendered into the chart's ConfigMap). Critical actions always
require a named human approver regardless of mode.
