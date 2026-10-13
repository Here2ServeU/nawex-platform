# Runbook: VM Migration Wave Cutover (VMware → OpenShift Virtualization)

| | |
|---|---|
| **Applies to** | Any MTV migration wave under `deploy/openshift/virtualization/waves/` |
| **Owner** | Migration engineer (R), engagement lead (A) |
| **Alerts** | `MigrationWaveStalled`, `MigrationFailuresSpike`, `MigrationFailureRatioHigh` → `#golden-migration-cutover` |
| **Dashboard** | Grafana → *Golden Platform — VM Migration* (`golden-migration`) |
| **Background** | [docs/modernization/vmware-to-openshift.md](../../../docs/modernization/vmware-to-openshift.md) |

## T-7 days — readiness

1. Wave manifests merged and synced by Argo CD; `Plan` shows `Ready`:

   ```bash
   oc get providers,networkmaps,storagemaps,plans -n openshift-mtv
   oc get plan <wave-plan> -n openshift-mtv -o jsonpath='{.status.conditions}' | jq
   ```

2. Capacity check: free CPU/RAM on virt-capable workers ≥ wave total + 20 %; storage free ≥ 1.3× wave size.
3. Source VMs: backups verified, snapshot count ≤ limit, CBT enabled (warm), VMware Tools running.
4. Change ticket approved (CAB); app owners confirmed for UAT; rollback owner named.
5. Warm waves: start precopy (create the `Migration` without `cutover`) — governor action
   `start_vm_migration` requires approval:

   ```bash
   golden security status            # confirm mode, kill switch released, pending approvals
   oc apply -f deploy/openshift/virtualization/waves/<wave>/migration.yaml
   ```

## T-0 — go / no-go (30 min before window)

- [ ] No firing critical alerts on target cluster or storage
- [ ] Precopies healthy (warm) — no `precopy_error` in `golden_migration_failures_total`
- [ ] App owner, on-call SRE, network and DBA present on the bridge
- [ ] Rollback plan reviewed ([rollback.md](./rollback.md))

Decision recorded in the change ticket and audit log.

## Cutover

1. **Quiesce** the application (maintenance page, stop batch jobs, drain queues).
2. **Final sync**
   - Warm: set the cutover time (MTV shuts the source VM down, copies the last delta, converts):

     ```bash
     oc patch migration <wave-migration> -n openshift-mtv --type merge \
       -p "{\"spec\":{\"cutover\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}"
     ```

   - Cold: create the `Migration` now (source VMs are powered off by MTV).
3. **Watch progress**

   ```bash
   oc get migration <wave-migration> -n openshift-mtv -w
   oc get vm,vmi -n <target-namespace>
   ```

   Grafana: wave progress → 100 %, failures flat. If a VM fails, follow the failure triage below.
4. **Start and verify target VMs**

   ```bash
   virtctl start <vm> -n <target-namespace>
   oc get vmi <vm> -n <target-namespace> -o jsonpath='{.status.interfaces}' | jq   # IPs via guest agent
   virtctl console <vm> -n <target-namespace>
   ```

5. **Switch traffic**: DNS records / load-balancer pools / firewall rules to target IPs (or confirm preserved IPs on the Multus VLAN).
6. **Validate**: smoke tests, UAT, monitoring scraping, backups scheduled, `virtctl migrate <vm>` succeeds.
7. **Close the window**: source VMs stay **powered off, not deleted**; mark hypercare start; post update in channel.

## Failure triage

| `reason` | Likely cause | Action |
|---|---|---|
| `vddk_timeout` | ESXi 902 blocked, VDDK image missing, slow datastore | Check `Provider` `vddkInitImage`, firewall, retry VM |
| `storage_capacity` | PVC pending / pool full | Expand pool or move VM to next wave |
| `network_mapping` | Port group missing from `NetworkMap` / NAD absent | Fix map, re-run |
| `guest_conversion` | virt-v2v failed (unsupported OS, encrypted disk, missing drivers) | Check conversion pod logs; remediate source or retain |
| `precopy_error` | CBT disabled / snapshot chain issue | Consolidate snapshots, enable CBT, restart warm migration |

```bash
oc logs -n openshift-mtv -l plan=<plan-uid> --tail=200
oc get events -n <target-namespace> --sort-by=.lastTimestamp | tail -30
```

If more than the agreed threshold (default 5 %) fails, or the window is at risk → **stop the wave** and go to [rollback.md](./rollback.md):

```bash
oc delete migration <wave-migration> -n openshift-mtv   # cancels in-flight transfers
```

## Exit criteria

- All wave VMs `Succeeded`, running, validated by app owners
- Traffic on target; SLOs green for the agreed observation period
- Change ticket updated; lessons learned captured for the next wave
