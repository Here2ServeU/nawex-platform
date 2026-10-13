# Platform add-ons

Cluster-level controllers the golden chart can integrate with. Every chart
feature that depends on one of them is **off by default**
(`deploy/helm/golden/values.yaml`); see [docs/platform/README.md](../../../docs/platform/README.md)
for the design notes.

| Add-on | Install | Manifests here | Chart / Terraform switch |
|---|---|---|---|
| Argo Rollouts | `helm install argo-rollouts argo/argo-rollouts -n argo-rollouts --create-namespace` | - | `rollouts.enabled` + `services.<name>.rollout.enabled` |
| KEDA | `helm install keda kedacore/keda -n keda --create-namespace` | - | `services.<name>.keda.enabled` |
| External Secrets Operator | `helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace` (annotate its ServiceAccount for IRSA / workload identity) | `external-secrets/` - one `ClusterSecretStore` per backend (apply exactly one; all are named `golden-secrets`) | `externalSecrets.enabled` |
| Karpenter (AWS) | Terraform: `deploy/terraform/modules/aws/eks` `karpenter_enabled = true` | `karpenter/` - `EC2NodeClass` + `general` and tainted `gpu` NodePools | `karpenter_enabled` |
| Velero (AWS) | Terraform: `velero_enabled = true` | `velero/` - daily + hourly `Schedule`, `Restore` example | `velero_enabled` |
| Kyverno | `helm install kyverno kyverno/kyverno -n kyverno --create-namespace` | `security/policies/kyverno/` | - |

Replace the placeholders (`golden-prod`, region, vault URL, project IDs) with
your environment's values before applying. All files are validated with
kubeconform by `scripts/ci/validate-infra.sh` (CRD kinds are schema-skipped).
