# VMware vSphere to OpenShift Virtualization

This directory is the Golden platform's template for moving virtual machines
from on-prem **VMware vSphere** to **OpenShift Virtualization** (KubeVirt),
using the **Migration Toolkit for Virtualization** (MTV, upstream
[Forklift](https://github.com/kubev2v/forklift)). Everything is plain YAML
assembled with kustomize, so it works with `oc apply -k`, Argo CD and Flux.

```text
virtualization/
├── kustomization.yaml          # renders operators + migration (used by CI)
├── operators/                  # stage 1: cluster-scoped install
│   ├── openshift-virtualization.yaml  # Namespace/OperatorGroup/Subscription (kubevirt-hyperconverged, channel stable)
│   ├── mtv.yaml                       # Namespace/OperatorGroup/Subscription (mtv-operator, channel release-v2.7)
│   ├── hyperconverged.yaml            # HyperConverged CR -> KubeVirt, CDI, ...
│   └── forklift-controller.yaml       # ForkliftController CR -> MTV controllers + UI
├── migration/                  # stage 2: one migration wave (example: wave-01)
│   ├── target-namespace.yaml          # golden-vms
│   ├── vsphere-secret.yaml            # PLACEHOLDER vCenter credentials
│   ├── providers.yaml                 # vsphere source Provider + openshift host Provider
│   ├── network-map.yaml               # port groups -> pod network / Multus
│   ├── storage-map.yaml               # datastores -> StorageClasses
│   ├── plan.yaml                      # warm Plan with the VMs in the wave
│   ├── migration.yaml                 # Migration (with cutover time)
│   └── sample-virtualmachine.yaml     # what a migrated VM looks like (reference only)
└── waves/                      # generated per-wave manifests (golden CLI output)
```

## Migration targets

MTV migrates into any OpenShift cluster that runs OpenShift Virtualization:

| Target | Notes |
| --- | --- |
| Self-managed OpenShift (bare metal, vSphere, other on-prem infrastructure) | The most common target. Workers need hardware virtualization: bare-metal nodes, or nested virtualization only where Red Hat supports it. |
| **ROSA** (Red Hat OpenShift Service on AWS) | Add a machine pool of **bare-metal EC2 instances** (for example `m5.metal`, `m5zn.metal`, `c5n.metal`). Standard virtualized EC2 instances can't run KubeVirt VMs. |
| **ARO** (Azure Red Hat OpenShift) | Support for OpenShift Virtualization on ARO is newer and is limited to specific worker VM sizes. Don't assume a general-purpose size such as Dsv5 with nested virtualization will work. Check the current ARO / OpenShift Virtualization support matrix for the approved sizes, or bare-metal options, before you size the cluster. |
| **OpenShift Dedicated on Google Cloud** | Needs bare-metal machine types (for example the C3 `-metal` family) where Red Hat lists them as supported. Verify the current OSD support matrix. |

Support for managed services changes often. Before you commit to a target,
confirm the instance or VM types, the OpenShift and MTV versions, and the
storage classes (RWX block storage is needed for live migration) against the
current Red Hat documentation. The Terraform landing zones in
`deploy/terraform/live/{aws,azure,gcp}` build EKS, AKS and GKE clusters for
the container platform. They do **not** provision ROSA, ARO or OSD, which you
create with `rosa`, `az aro` or OCM.

## End-to-end flow

1. **Install the operators.** Approve the InstallPlans (`installPlanApproval: Manual`)
   and wait for the operators to come up:

   ```bash
   oc apply -k deploy/openshift/virtualization/operators
   oc get installplan -n openshift-cnv; oc get installplan -n openshift-mtv
   oc patch installplan <name> -n <ns> --type merge -p '{"spec":{"approved":true}}'
   oc wait hyperconverged/kubevirt-hyperconverged -n openshift-cnv \
     --for=condition=Available --timeout=30m
   ```

   If `oc apply -k` fails on the first run because the HyperConverged or
   ForkliftController CRDs don't exist yet, run it again once the operators
   are installed. Argo CD handles this with the
   `SkipDryRunOnMissingResource` annotation on both CRs.

2. **Create the providers.** Put the real vCenter credentials in
   `vsphere-credentials`, ideally from External Secrets or Vault. Build the
   VDDK init image from VMware's VDDK SDK and push it to your own registry.
   `providers.yaml` registers vCenter as the source and the host cluster as
   the destination. Check that the provider status shows `Ready` and that
   inventory has loaded:
   `oc get provider -n openshift-mtv`.

3. **Map networks and storage.** `network-map.yaml` maps each vSphere port
   group to the pod network or to a Multus `NetworkAttachmentDefinition`.
   `storage-map.yaml` maps each datastore to a StorageClass. Use
   RWX + Block for VMs that need live migration.

4. **Plan each wave.** Each `Plan` lists the VMs of one wave, sets the
   `targetNamespace` and turns on `warm: true` to keep downtime short. Group
   waves by dependency and risk: start with stateless and low-risk VMs and
   leave databases and appliances for later. Review MTV's validation
   warnings with `oc get plan wave-01 -n openshift-mtv -o yaml`. They cover
   things like unsupported disks, RDMs, snapshots, shared disks and
   missing VMware Tools.

5. **Migrate.** Create the `Migration`. For a warm migration, MTV
   pre-copies disks while the source VMs keep running. At the `cutover`
   time it shuts down the source VMs, copies the final delta, converts the
   guests with virt-v2v and starts them on OpenShift.

6. **Validate.** Check that the VMs are `Running`
   (`oc get vm,vmi -n golden-vms`). Then confirm guest agent connectivity,
   application health checks, DNS/IP (`preserveStaticIPs`), monitoring and
   backups. Run the app owner's smoke tests before you declare success.

7. **Cutover or roll back.**
   - *Cutover*: update DNS and load balancers, then decommission the source VMs
     after the agreed soak period. The source VMs stay powered off in
     vSphere until then.
   - *Rollback*: stop the migrated VM (`virtctl stop`), power the source VM
     back on in vCenter and revert DNS. MTV never deletes the source VMs.
     Delete the target VM and its PVCs before you retry the wave.

## Generating waves with the golden CLI

You don't write wave manifests by hand. The `golden` CLI reads a vSphere
inventory export (RVTools) and generates one directory per wave:

```bash
golden migrate plan --inventory rvtools.csv
# -> deploy/openshift/virtualization/waves/<wave>/{kustomization.yaml,plan.yaml,network-map.yaml,storage-map.yaml,migration.yaml}
oc apply -k deploy/openshift/virtualization/waves/<wave>
```

The `migration-planner` service (`golden serve migration-planner`, port 8097,
deployed by `deploy/helm/golden`) exposes the same planning logic over HTTP.

## Validation

`scripts/ci/validate-infra.sh` renders this directory with `kubectl kustomize`
and validates it with kubeconform. The OpenShift, OLM, KubeVirt and Forklift
CRDs have no public JSON schemas, so CI skips them with
`-ignore-missing-schemas`. Only the core Kubernetes objects are
schema-checked.

Never commit real credentials. `vsphere-secret.yaml` contains only
`REPLACE_ME` placeholders.
