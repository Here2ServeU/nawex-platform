# Kyverno admission policies

Admission-time counterparts of the CI-time OPA policies in `../opa/`
(defence in depth: OPA gates manifests and Terraform plans in the pipeline;
Kyverno enforces in the cluster, including for anything applied out of band).

| Policy | Mode | Purpose |
|---|---|---|
| `verify-images.yaml` | Enforce | `ghcr.io/here2serveu/*` must be keyless-signed (and SBOM-attested) by this repo's `containers.yml` workflow on `main` / `v*` tags; tags are pinned to the verified digest |
| `disallow-latest-tag.yaml` | Enforce | No `:latest` and no untagged images (same rule as `k8s-security.rego`) |
| `require-labels.yaml` | Audit | `app.kubernetes.io/name` + `part-of` on workloads in golden namespaces |

Install Kyverno (`helm install kyverno kyverno/kyverno -n kyverno --create-namespace`),
then `kubectl apply -f security/policies/kyverno/`. Test locally with the
Kyverno CLI: `kyverno apply security/policies/kyverno/ --resource <rendered.yaml>`.

Verify an image by hand exactly as the policy does:

```bash
cosign verify ghcr.io/here2serveu/golden-platform@sha256:<digest> \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp '^https://github\.com/Here2ServeU/nawex-platform/\.github/workflows/containers\.yml@refs/(heads/main|tags/v.+)$'
```
