# Backup and Restore with Velero (EKS)

Owner: Platform SRE. Applies to clusters built from `deploy/terraform/modules/aws/eks` with
`velero_enabled = true`.

## What is protected

| Item | Mechanism | Where |
|---|---|---|
| Kubernetes objects in `golden`, `migrated-vms` (+ cluster-scoped objects they reference) | Velero backup tarball | S3 bucket `<name>-velero-backups` (SSE-KMS, versioned, public access blocked, TLS-only) |
| PersistentVolumes (gp3, EBS CSI) | EBS snapshots | Same region (copy to a second region for regional DR, see below) |
| Schedules | `golden-daily` 02:00 UTC, PVs + objects, TTL 30 days; `golden-hourly-objects` hourly, objects only, TTL 72 h | `deploy/k8s/platform-addons/velero/schedule-daily.yaml` |

Out of scope: managed data stores (RDS, ElastiCache, MSK). They have their own backups
(`ops/runbooks/playbooks/db_failover_postgres.md`). Secrets synced by External Secrets
come back from the secret backend, not from the backup.

**Targets:** RPO is 1 h for Kubernetes objects and 24 h for volume data. RTO is 60 min for
a namespace restore into an existing cluster, or 4 h when a new cluster has to be built
first (Terraform apply about 25 min, add-ons, then restore).

## Prerequisites

```bash
aws eks update-kubeconfig --name <cluster> --region <region>
velero version                                  # client and server versions should match
velero backup-location get                      # PHASE must be Available
velero snapshot-location get
terraform -chdir=deploy/terraform/live/aws/<env> output velero_bucket_name
```

If the BackupStorageLocation is `Unavailable`, check the IRSA annotation on
`velero/velero-server`, the role's trust policy (`system:serviceaccount:velero:velero-server`),
and whether the key policy allows the role to use the KMS key (`velero_kms_key_arn`).

## 1. Backup verification drill (monthly, and after every Velero upgrade)

A backup that has never been restored is not a backup. The drill restores into a scratch
namespace and measures the real RPO and RTO.

1. **Take a fresh on-demand backup** and record the start time (T0):
   ```bash
   T0=$(date -u +%s)
   velero backup create drill-$(date -u +%Y%m%d%H%M) --from-schedule golden-daily --wait
   velero backup describe drill-<ts> --details     # Phase: Completed, Errors: 0, Warnings reviewed
   velero backup logs drill-<ts> | grep -iE "error|warn" || true
   ```
2. **Check the latest scheduled backups** completed on time (this is the RPO you actually have):
   ```bash
   velero backup get --selector golden.io/backup-tier=daily  | head -5
   velero backup get --selector golden.io/backup-tier=hourly | head -5
   ```
   Alert condition: there is no `Completed` daily backup from the last 26 h, or no hourly
   backup from the last 2 h. Prometheus can catch this with
   `time() - velero_backup_last_successful_timestamp{schedule="golden-daily"} > 93600`.
3. **Restore into a scratch namespace** using
   `deploy/k8s/platform-addons/velero/restore-example.yaml`. Set `backupName`; the
   `namespaceMapping` sends `golden` to `golden-restore`:
   ```bash
   kubectl apply -f deploy/k8s/platform-addons/velero/restore-example.yaml
   velero restore describe golden-restore-drill --details
   kubectl -n golden-restore get deploy,rollout,svc,pvc,externalsecret
   ```
4. **Validate the workload**, not just the objects:
   ```bash
   kubectl -n golden-restore rollout status deploy/<release>-golden-api --timeout=10m
   kubectl -n golden-restore port-forward svc/<release>-golden-api 18000:8000 &
   curl -fsS localhost:18000/health && curl -fsS localhost:18000/ready
   ```
   For each restored PVC, check that it is `Bound` and that the application can read its
   data (for example, the agent-ops ledger under `/data/agentops`).
5. **Record the RTO.** `T1=$(date -u +%s); echo "RTO seconds: $((T1-T0))"`. Also record the
   RPO, which is T0 minus the timestamp of the newest backup restored. Log both in the DR
   drill register (`ops/runbooks/dr/`).
6. **Clean up:** `kubectl delete ns golden-restore` and `velero restore delete golden-restore-drill`.
   Delete the on-demand backup too with `velero backup delete drill-<ts>` (this also deletes
   its EBS snapshots).

## 2. Restore procedures

### 2a. Single namespace or a few objects lost (cluster healthy)

1. Pause GitOps sync for the application so Argo CD does not race the restore.
2. Choose the newest backup taken before the incident: `velero backup get`.
3. Restore only what is missing:
   ```bash
   velero restore create --from-backup <backup> \
     --include-namespaces golden \
     --include-resources persistentvolumeclaims,persistentvolumes,configmaps \
     --existing-resource-policy none --wait
   ```
   `--existing-resource-policy none` leaves live objects alone. Use `update` only when
   you mean to overwrite them.
4. Resume GitOps sync. Git is the source of truth for manifests, so Velero mostly brings
   back state: PVCs/PVs and anything created at runtime.

### 2b. Full cluster loss (regional or account incident)

1. Rebuild the cluster with Terraform (`deploy/terraform/live/aws/<env>`). Keep the same
   `velero_bucket_name` so the new Velero reads the existing bucket. To stop the new
   cluster from writing into the bucket during recovery, set the BackupStorageLocation to
   `accessMode: ReadOnly`:
   ```bash
   kubectl -n velero patch backupstoragelocation default --type merge -p '{"spec":{"accessMode":"ReadOnly"}}'
   ```
2. Install the platform add-ons that own CRDs before restoring: External Secrets, Argo
   Rollouts, KEDA, and the Prometheus Operator. Otherwise their custom resources are
   skipped.
3. Restore:
   ```bash
   velero restore create dr-$(date -u +%Y%m%d%H%M) --from-backup <latest-daily> \
     --include-namespaces golden,migrated-vms --restore-volumes=true --wait
   ```
4. Point DNS / ingress at the new cluster and run the smoke checks from step 1.4 against
   `golden`.
5. Set the BackupStorageLocation back to `ReadWrite` and confirm the next scheduled backup
   completes.

### Regional DR

EBS snapshots are regional. For cross-region recovery:

- Enable S3 Cross-Region Replication on the bucket, using a KMS key in the target region.
- Copy snapshots with AWS Backup or a scheduled `aws ec2 copy-snapshot`.

Restoring in the second region also needs a VolumeSnapshotLocation for that region.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Backup `PartiallyFailed` with snapshot errors | IRSA policy is missing `ec2:CreateSnapshot`/`CreateTags` for the region, or the volume is encrypted with a CMK the role cannot use. Grant `kms:CreateGrant` on that key. |
| Restore leaves PVC `Pending` | The StorageClass name differs in the new cluster. Use `velero restore create ... --storage-class-mappings` (ConfigMap `change-storage-class-config`). |
| Custom resources skipped | Their CRD was not installed before the restore. Install the add-on, then restore again with `--include-resources <crd>`. |
| Pods restart in a loop after restore | The API keys Secret is missing. Check that the `ExternalSecret` is `SecretSynced`, or restore the Secret explicitly. |

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
