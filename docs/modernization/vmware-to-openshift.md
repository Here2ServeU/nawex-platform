# VMware vSphere → OpenShift Virtualization Runbook

Detailed runbook for rehosting virtual machines from on-prem VMware vSphere to Red Hat OpenShift
Virtualization (KubeVirt) with the **Migration Toolkit for Virtualization (MTV, upstream Forklift)**.
Phases and roles are described in the [modernization playbook](./README.md).

Platform pieces used here:

| Piece | Location |
|---|---|
| Assessment, wave planner, manifest generator | `golden migrate assess\|plan\|manifests`; service `migration-planner` :8097 |
| API | `POST /api/v1/migration/assess`, `/api/v1/migration/plan`, `/api/v1/migration/manifests` |
| Operators (OpenShift Virtualization, MTV) | `deploy/openshift/virtualization/operators/` |
| Providers, network/storage maps | `deploy/openshift/virtualization/migration/` |
| Per-wave Plans / Migrations | `deploy/openshift/virtualization/waves/` |
| Alerts / dashboard | `observability/prometheus/rules/migration_rules.yml`, `golden-migration.json` |
| Operational runbooks | `ops/runbooks/migration/{cutover,rollback}.md` |

## 1. Prerequisites

**OpenShift**

- OpenShift Container Platform **4.14+** on bare-metal workers (or nested-virt capable nodes for labs)
  with CPU virtualization extensions (Intel VT-x / AMD-V) enabled.
- **OpenShift Virtualization** operator (HyperConverged CR) and **MTV** operator (ForkliftController CR)
  installed from `deploy/openshift/virtualization/operators/`.
- **Storage**: ODF (Ceph RBD, block mode, RWX) or another CSI driver with **RWX** block volumes so VMs
  can live-migrate; a default `StorageClass` for VM disks; capacity ≥ 1.3× the provisioned size of the wave.
- **Networking**: NMState operator + **Multus** `NetworkAttachmentDefinition`s for each VLAN/port group
  that must be preserved (bridge or OVN-K localnet secondary networks); pod network for the rest.
- Capacity: sum of wave vCPU/RAM plus 20 % headroom for live migration and node drains.

**VMware**

- vCenter 6.5+ / ESXi 6.5+ (7.x/8.x recommended), reachable from the cluster on 443 (vCenter) and 902 (ESXi NFC).
- **VDDK image**: download the VMware Virtual Disk Development Kit, build and push the init image
  (`FROM registry.access.redhat.com/ubi8/ubi-minimal` + `vmware-vix-disklib-distrib/`) to an internal
  registry; reference it in the vSphere `Provider` (`vddkInitImage`). Without VDDK transfers are far slower.
- **vCenter service account** with at minimum: *Virtual machine → Provisioning → Allow disk access, Allow read-only
  disk access, Allow virtual machine download*; *Virtual machine → Snapshot management → Create/Remove snapshot*;
  *Datastore → Browse datastore, Low level file operations*; *Sessions → Validate session*; read-only on the
  datacenter. Store credentials in a Secret referenced by the `Provider` — never in Git.
- **Changed Block Tracking (CBT)** enabled on every VM planned for **warm** migration.
- VMware Tools running (for clean shutdown and IP reporting).

## 2. Inventory export

The planner (`golden.migration.inventory.load_inventory`) accepts:

- a **directory** of RVTools CSV exports containing `*vInfo*.csv` and optionally `*vDisk*.csv` and `*vNetwork*.csv`,
- a single RVTools **vInfo CSV**, or
- **JSON** in the platform VM schema (e.g. produced from `govc` output by your own exporter).

```bash
# RVTools (Windows): File → Export all to CSV, then copy vInfo / vDisk / vNetwork into one folder
golden migrate assess --inventory exports/rvtools/ > build/assessment.json

# govc (any OS): collect, convert to the VM JSON schema, then assess
export GOVC_URL=https://vcenter.example.local GOVC_USERNAME=svc-mtv@vsphere.local GOVC_PASSWORD=...
govc vm.info -json -r '/*/vm/**' > exports/govc-vminfo.json
golden migrate assess --inventory exports/vms.json > build/assessment.json
```

No vCenter at hand? The planner ships a synthetic estate (`golden.migration.inventory.sample_inventory`)
for demos and tests.

Fields used: VM name, power state, guest OS, firmware (BIOS/EFI), vCPU, memory, disks (size, mode,
sharing, RDM physical/virtual), NICs (port group, MAC, IPs), snapshots, VMware Tools status, encryption,
passthrough devices, vGPU, and application / criticality tags.

## 3. Assessment rules

`golden.migration.assessment.assess_vm` classifies each finding as **blocker** (cannot migrate as-is),
**warning** (migrates, needs action) or **info**, and each VM as `ready`, `needs_remediation` or `blocked`,
with a 1–10 complexity score and a recommended cold/warm method.

**Blockers**

| Rule ID | Condition | Typical remediation |
|---|---|---|
| `RDM_PHYSICAL` | Physical-compatibility-mode RDM disk | Convert to VMDK (Storage vMotion) or re-present the LUN to OpenShift as a PV |
| `SHARED_DISK` | Multi-writer / shared disk (e.g. Oracle RAC, WSFC) | Re-architect the cluster or migrate at the application level |
| `INDEPENDENT_DISK` | Independent (persistent / non-persistent) disk — excluded from snapshots | Change disk mode to dependent |
| `ENCRYPTED_VM` | vSphere VM Encryption | Decrypt before migration; rely on encrypted storage on the target |
| `PASSTHROUGH` | PCI / USB / serial passthrough devices | Replace with network-attached alternatives or keep on vSphere |
| `VGPU` | NVIDIA vGPU | Plan GPU worker nodes with passthrough/mediated devices, or replatform |
| `UNSUPPORTED_OS` | End-of-life guest (Windows Server 2003/2008, Windows XP/7, CentOS/RHEL 5–6, Solaris, FreeBSD) | Upgrade the OS, replatform, or retain |

**Warnings**

| Rule ID | Condition | Action |
|---|---|---|
| `RDM_VIRTUAL` | Virtual-mode RDM | Migrates as a regular disk; validate data and performance |
| `UNVERIFIED_OS` | Guest OS not on the certified list | Test in the pilot wave before scheduling |
| `SNAPSHOTS` | Snapshots present | Consolidate before the wave (long chains slow or break transfers); keep only the pre-migration snapshot |
| `NO_VMWARE_TOOLS` | VMware Tools not installed / not running | Clean shutdown and IP discovery may fail — install Tools or plan manual IP config |
| `LARGE_VM` | > 16 vCPU or > 256 GB RAM | Confirm node capacity and NUMA placement; dedicated window |
| `LARGE_DISKS` | > 2 TB total disk | Prefer warm migration; check storage throughput |

**Info**

| Rule ID | Condition | Action |
|---|---|---|
| `VIRTIO_DRIVERS` | Windows guest | virt-v2v injects VirtIO drivers; verify boot in the pilot |
| `STATIC_IP` | IPs on vSphere networks | Map the port group to a Multus NAD on the same VLAN; MTV preserves MACs — verify guest network config |
| `UEFI` | EFI firmware | Preserved by MTV; enable Secure Boot only if the source had it |

Recommended method: **warm** when total disk ≥ 500 GB or criticality is `high` / `mission_critical`,
otherwise **cold**. Warm migration additionally requires Changed Block Tracking (CBT) on the VM —
check it during wave readiness.

Output: per-VM readiness, findings, complexity, method and estimated transfer time (from VM size and
the configured bandwidth, default 10 Gbps), plus a summary by application.

## 4. Wave planning

```bash
golden migrate plan --inventory exports/rvtools/ > build/waves.json
```

Grouping and ordering heuristics:

1. **Application / dependency grouping** — VMs of the same app (tags, folders, naming, observed flows)
   move together; tightly coupled apps share a wave.
2. **Criticality** — pilot with non-production and low-criticality apps; tier-1 apps after ≥ 2 clean waves.
3. **Size** — cap total TB and VM count per wave to fit the transfer window and storage throughput.
4. **Method**
   - **Cold** — VM powered off for the whole copy. Simple, consistent; downtime ≈ copy time. Default for
     small VMs and non-production.
   - **Warm** — CBT-based precopies while the VM runs, then a short final cutover (`cutover` timestamp on the
     `Migration` CR). Use for large disks and tight downtime windows; requires CBT and snapshot headroom.
5. **Windows** — align with change windows and app owners' availability for UAT.

## 5. Generated MTV resources

```bash
golden migrate manifests --inventory exports/rvtools/ \
  --out deploy/openshift/virtualization/waves/
```

Generated (namespace `openshift-mtv` unless configured):

- `Provider` (vSphere: URL, credential Secret ref, `vddkInitImage`; host: the OpenShift cluster)
- `NetworkMap` — port group → `pod` network or `multus` NAD
- `StorageMap` — datastore → `StorageClass` (block/RWX for live migration)
- `Plan` — VM list, target namespace, `warm: true|false`, optional hooks (pre/post Ansible)
- `Migration` — references the Plan; for warm migrations the `cutover` time is set at go-time

Example (abridged):

```yaml
apiVersion: forklift.konveyor.io/v1beta1
kind: Plan
metadata:
  name: wave-01-payments
  namespace: openshift-mtv
spec:
  warm: true
  provider:
    source: {name: vsphere-prod, namespace: openshift-mtv}
    destination: {name: host, namespace: openshift-mtv}
  map:
    network: {name: wave-01-netmap, namespace: openshift-mtv}
    storage: {name: wave-01-storagemap, namespace: openshift-mtv}
  targetNamespace: payments
  vms:
    - name: pay-app-01
    - name: pay-db-01
---
apiVersion: forklift.konveyor.io/v1beta1
kind: Migration
metadata:
  name: wave-01-payments-run1
  namespace: openshift-mtv
spec:
  plan: {name: wave-01-payments, namespace: openshift-mtv}
  # cutover: "2026-11-14T02:00:00Z"   # set at go-time for warm migrations
```

Commit the wave directory; Argo CD (`deploy/gitops`) applies it. `Migration` objects are created only
after approval — `start_vm_migration` and `vm_cutover` are **critical** actions in the action governor.

## 6. Cutover checklist (summary)

Full procedure: [ops/runbooks/migration/cutover.md](../../ops/runbooks/migration/cutover.md).

- [ ] Change approved; go/no-go meeting held; app owners and on-call present
- [ ] Backups of source VMs verified; snapshot count within limit
- [ ] Plan `Ready`, providers `Ready`, maps validated; capacity checked
- [ ] Warm: precopies healthy for ≥ 24 h; set `cutover` timestamp
- [ ] Source app quiesced; final sync complete; VM `Succeeded`
- [ ] Target VM boots; guest agent reports IPs; services healthy
- [ ] DNS / load balancer / firewall switched; monitoring green
- [ ] Source VMs **powered off, not deleted**; hypercare window started

## 7. Validation

- Boot and guest agent (`qemu-guest-agent`) running; virtio drivers loaded (Windows: Device Manager).
- Network: IP, gateway, DNS, VLAN reachability, firewall rules, MAC-bound licences.
- Storage: all disks present, filesystem consistency, application data checksums for critical datasets.
- Application: smoke tests, UAT sign-off, performance vs pre-migration baseline (latency, throughput).
- Operations: monitoring scraping, logs shipping, backups (OADP / vendor) succeed, live migration works
  (`virtctl migrate <vm>`).

## 8. Rollback

Full procedure: [ops/runbooks/migration/rollback.md](../../ops/runbooks/migration/rollback.md).

Rollback is possible while the source VM still exists (until decommission):
stop the target VM → revert DNS/LB → power on the source VM (or revert to the pre-migration snapshot) →
validate → record the failure reason (feeds `golden_migration_failures_total{reason}` and the planner).

## 9. Decommission

After the hypercare window (typically 2–4 weeks) and app-owner sign-off:

- Delete source VMs and their snapshots; reclaim datastore capacity.
- Remove VMs from backup jobs, monitoring, CMDB; update DR runbooks.
- Return vSphere / guest OS licences; update the FinOps report.
- Archive `Plan`/`Migration` CRs and the audit log as engagement evidence.

## 10. Observability & SLOs

| Metric | Meaning |
|---|---|
| `golden_migration_vms_total{status}` | VMs by status (`pending`, `running`, `succeeded`, `failed`, `rolled_back`) |
| `golden_migration_wave_progress_ratio{wave}` | 0..1 progress per wave |
| `golden_migration_failures_total{reason}` | Failures by reason (`vddk_timeout`, `storage_capacity`, `network_mapping`, `guest_conversion`, `precopy_error`, …) |
| `golden_migration_duration_seconds` | Per-VM end-to-end migration duration (histogram) |

Alerts (`migration_rules.yml`): `MigrationPlannerDown`, `MigrationFailuresSpike`,
`MigrationFailureRatioHigh`, `MigrationWaveStalled`, `MigrationDurationHigh` → Slack `#golden-migration-cutover`.
MTV's own controller metrics (`mtv_*`) can be scraped from `openshift-mtv` with a ServiceMonitor.

SLOs per wave:

- ≥ 95 % of VMs succeed on first attempt; 100 % after remediation
- Downtime per VM ≤ agreed window (cold: copy time; warm: ≤ 30 min cutover)
- Zero data loss (checksums on critical datasets)
- Post-cutover application SLOs ≥ pre-migration baseline for 72 h
