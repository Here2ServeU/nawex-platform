"""Migration readiness assessment for VMware → OpenShift Virtualization (MTV).

Each VM is checked against rules derived from MTV / OpenShift Virtualization constraints and field
experience. Findings are ``blocker`` (cannot migrate as-is), ``warning`` (migrates, needs action) or
``info``. Readiness is ``ready``, ``needs_remediation`` or ``blocked``.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from golden.migration.inventory import VM

SUPPORTED_GUESTS = [
    r"red hat enterprise linux [789]",
    r"rhel ?[789]",
    r"centos (7|stream)",
    r"rocky",
    r"alma",
    r"windows server (2012 r2|2016|2019|2022|2025)",
    r"windows 1[01]",
    r"sles 1[25]",
    r"suse",
    r"ubuntu",
    r"debian",
    r"oracle linux [789]",
    r"fedora",
]
EOL_GUESTS = [
    r"windows server 2008",
    r"windows server 2003",
    r"windows xp",
    r"windows 7",
    r"centos [56]",
    r"red hat enterprise linux [56]",
    r"solaris",
    r"freebsd",
]

LARGE_VCPU = 16
LARGE_MEMORY_GB = 256
LARGE_DISK_GB = 2048
WARM_THRESHOLD_GB = 500


@dataclass
class Finding:
    code: str
    severity: str  # blocker | warning | info
    message: str
    remediation: str


@dataclass
class VMAssessment:
    vm: str
    application: str
    criticality: str
    readiness: str
    complexity: int  # 1 (trivial) .. 10 (hard)
    migration_type: str  # cold | warm
    estimated_hours: float
    total_disk_gb: float
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _match(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def assess_vm(vm: VM, *, bandwidth_gbps: float = 10.0) -> VMAssessment:
    f: list[Finding] = []
    os_name = vm.guest_os or ""

    # --- blockers -----------------------------------------------------------
    for d in vm.disks:
        if d.rdm and d.rdm_physical:
            f.append(
                Finding(
                    "RDM_PHYSICAL",
                    "blocker",
                    f"{d.label} is a physical-mode RDM",
                    "Convert to VMDK (storage vMotion) or re-present the LUN to OpenShift via CSI",
                )
            )
        elif d.rdm:
            f.append(
                Finding(
                    "RDM_VIRTUAL",
                    "warning",
                    f"{d.label} is a virtual-mode RDM",
                    "Storage vMotion to a VMDK before migration",
                )
            )
        if d.shared:
            f.append(
                Finding(
                    "SHARED_DISK",
                    "blocker",
                    f"{d.label} uses multi-writer sharing",
                    "Re-architect clustering (e.g. WSFC/Oracle RAC) with shared RWX block PVCs",
                )
            )
        if d.mode.startswith("independent"):
            f.append(
                Finding(
                    "INDEPENDENT_DISK",
                    "blocker",
                    f"{d.label} is in {d.mode} mode",
                    "Switch disk to dependent mode; independent disks are skipped by snapshots/CBT",
                )
            )
    if vm.encrypted:
        f.append(
            Finding(
                "ENCRYPTED_VM",
                "blocker",
                "VM is encrypted with vSphere VM Encryption",
                "Decrypt in vSphere, migrate, then use storage-level encryption (e.g. ODF/LUKS)",
            )
        )
    if vm.passthrough_devices:
        f.append(
            Finding(
                "PASSTHROUGH",
                "blocker",
                f"{vm.passthrough_devices} PCI/USB passthrough device(s)",
                "Remove the device or plan host-device passthrough on the target node",
            )
        )
    if vm.vgpu:
        f.append(
            Finding(
                "VGPU",
                "blocker",
                "VM uses NVIDIA vGPU",
                "Recreate with the NVIDIA GPU Operator mediated devices on OpenShift",
            )
        )
    if _match(EOL_GUESTS, os_name):
        f.append(
            Finding(
                "UNSUPPORTED_OS",
                "blocker",
                f"Guest OS '{os_name}' is end-of-life/unsupported",
                "Upgrade the guest OS or replatform the workload before migration",
            )
        )
    elif os_name and not _match(SUPPORTED_GUESTS, os_name):
        f.append(
            Finding(
                "UNVERIFIED_OS",
                "warning",
                f"Guest OS '{os_name}' is not on the certified list",
                "Validate in a pilot wave; check virtio driver availability",
            )
        )

    # --- warnings -----------------------------------------------------------
    if vm.snapshots:
        f.append(
            Finding(
                "SNAPSHOTS",
                "warning",
                f"{vm.snapshots} snapshot(s) present",
                "Consolidate/delete snapshots before migration",
            )
        )
    if "notinstalled" in vm.tools_status.lower() or "notrunning" in vm.tools_status.lower():
        f.append(
            Finding(
                "NO_VMWARE_TOOLS",
                "warning",
                "VMware Tools not running",
                "Install tools so MTV can read guest IPs and shut down cleanly",
            )
        )
    if "windows" in os_name.lower():
        f.append(
            Finding(
                "VIRTIO_DRIVERS",
                "info",
                "Windows guest needs VirtIO drivers",
                "MTV injects virtio-win via virt-v2v; verify boot in the pilot wave",
            )
        )
    if vm.cpus > LARGE_VCPU or vm.memory_gb > LARGE_MEMORY_GB:
        f.append(
            Finding(
                "LARGE_VM",
                "warning",
                f"{vm.cpus} vCPU / {vm.memory_gb} GB RAM",
                "Confirm target node capacity and NUMA placement; consider dedicated CPU",
            )
        )
    if vm.total_disk_gb > LARGE_DISK_GB:
        f.append(
            Finding(
                "LARGE_DISKS",
                "warning",
                f"{vm.total_disk_gb:.0f} GB of disk",
                "Use warm migration and schedule cutover in a maintenance window",
            )
        )
    if any(n.ip for n in vm.nics):
        f.append(
            Finding(
                "STATIC_IP",
                "info",
                "VM has IP addresses on vSphere networks",
                "Map to a Multus NetworkAttachmentDefinition to preserve L2/IP, or plan re-IP",
            )
        )
    if vm.firmware == "efi":
        f.append(
            Finding(
                "UEFI", "info", "UEFI firmware", "MTV preserves EFI; enable Secure Boot only if source had it"
            )
        )

    blockers = sum(1 for x in f if x.severity == "blocker")
    warnings = sum(1 for x in f if x.severity == "warning")
    readiness = "blocked" if blockers else ("needs_remediation" if warnings else "ready")
    complexity = min(
        10, 1 + 3 * blockers + warnings + (1 if vm.criticality in {"high", "mission_critical"} else 0)
    )
    warm = vm.total_disk_gb >= WARM_THRESHOLD_GB or vm.criticality in {"high", "mission_critical"}
    # transfer at ~60% of link speed + fixed conversion overhead
    transfer_hours = vm.total_disk_gb * 8 / (bandwidth_gbps * 0.6 * 3600)
    return VMAssessment(
        vm=vm.name,
        application=vm.application or "unassigned",
        criticality=vm.criticality,
        readiness=readiness,
        complexity=complexity,
        migration_type="warm" if warm else "cold",
        estimated_hours=round(transfer_hours + 0.5, 2),
        total_disk_gb=vm.total_disk_gb,
        findings=f,
    )


def assess_inventory(vms: Iterable[VM], *, bandwidth_gbps: float = 10.0) -> dict[str, Any]:
    results = [assess_vm(vm, bandwidth_gbps=bandwidth_gbps) for vm in vms]
    by_readiness = Counter(r.readiness for r in results)
    by_code = Counter(fd.code for r in results for fd in r.findings if fd.severity != "info")
    return {
        "summary": {
            "vms": len(results),
            "ready": by_readiness.get("ready", 0),
            "needs_remediation": by_readiness.get("needs_remediation", 0),
            "blocked": by_readiness.get("blocked", 0),
            "total_disk_tb": round(sum(r.total_disk_gb for r in results) / 1024, 2),
            "top_issues": by_code.most_common(5),
        },
        "vms": [r.to_dict() for r in results],
    }
