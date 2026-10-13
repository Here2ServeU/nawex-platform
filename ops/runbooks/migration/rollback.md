# Runbook: VM Migration Rollback

| | |
|---|---|
| **Applies to** | Any migrated VM / wave **before decommission** of the source VMs |
| **Decision** | Engagement lead / CAB (A), migration engineer (R) |
| **Governor action** | `vm_rollback` — *critical*, requires a named human approver |
| **Time objective** | Service restored on source within 30 min of the decision |

## When to roll back

- Target VM fails to boot or convert and cannot be fixed inside the window
- Application validation / UAT fails, or performance is materially worse than baseline
- Data inconsistency detected
- Cutover window about to be exceeded (`MigrationWaveStalled`, `MigrationFailuresSpike`)

## Procedure

1. **Declare** rollback on the bridge and in `#golden-migration-cutover`; record it in the change ticket.
2. **Stop in-flight work** (if the wave is still running):

   ```bash
   oc delete migration <wave-migration> -n openshift-mtv
   ```

3. **Stop the target VM(s)** so two copies never run with the same IP/MAC:

   ```bash
   virtctl stop <vm> -n <target-namespace>
   ```

4. **Revert traffic**: DNS / load-balancer / firewall back to the source IPs.
5. **Restore the source VM**:
   - Power it on in vCenter (`govc vm.power -on <vm>`).
   - If the source was modified (e.g. cutover partially applied changes), revert to the pre-migration snapshot first
     (`govc snapshot.revert -vm <vm> pre-migration`).
6. **Validate** on source: application health checks, monitoring, app owner confirmation.
7. **Record the reason** — it is counted in `golden_migration_failures_total{reason}` and fed back into the
   planner so the VM is re-assessed:

   ```bash
   golden migrate assess --inventory <latest-export>   # re-run after remediation
   ```

8. **Clean up the target** after confirmation (keep for forensics if needed):

   ```bash
   oc delete vm <vm> -n <target-namespace>
   oc get pvc -n <target-namespace> -l vm.kubevirt.io/name=<vm>   # delete only after root cause is understood
   ```

## Post-rollback

- Root-cause analysis within 2 business days; update the assessment rules if a new blocker was found.
- Re-plan the VM into a later wave (`golden migrate plan`).
- Keep the source snapshot until the next successful attempt.
