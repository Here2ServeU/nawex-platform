"""VMware vSphere inventory model and loaders.

Supported sources:

* **RVTools** CSV exports (``vInfo`` required; ``vDisk`` and ``vNetwork`` optional) — the de-facto
  standard export in VMware estates.
* Platform JSON (``list[VM]`` as produced by :func:`to_json` or ``govc`` post-processing).
* :func:`sample_inventory` — a realistic synthetic estate for demos and tests.
"""

from __future__ import annotations

import csv
import json
import random
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Disk:
    label: str
    capacity_gb: float
    datastore: str = ""
    mode: str = "persistent"  # persistent | independent_persistent | independent_nonpersistent
    rdm: bool = False
    rdm_physical: bool = False
    shared: bool = False  # multi-writer


@dataclass
class Nic:
    network: str
    ip: str = ""
    mac: str = ""


@dataclass
class VM:
    name: str
    guest_os: str
    cpus: int
    memory_mb: int
    power_state: str = "poweredOn"
    firmware: str = "bios"
    disks: list[Disk] = field(default_factory=list)
    nics: list[Nic] = field(default_factory=list)
    snapshots: int = 0
    tools_status: str = "toolsOk"
    encrypted: bool = False
    passthrough_devices: int = 0
    vgpu: bool = False
    datacenter: str = ""
    cluster: str = ""
    host: str = ""
    application: str = ""
    criticality: str = "medium"  # low | medium | high | mission_critical
    depends_on: list[str] = field(default_factory=list)

    @property
    def total_disk_gb(self) -> float:
        return round(sum(d.capacity_gb for d in self.disks), 1)

    @property
    def memory_gb(self) -> float:
        return round(self.memory_mb / 1024, 1)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VM:
        data = dict(data)
        data["disks"] = [Disk(**d) for d in data.get("disks", [])]
        data["nics"] = [Nic(**n) for n in data.get("nics", [])]
        return cls(**data)


# ----------------------------------------------------------------------------- RVTools
def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"true", "yes", "1"}


def _int(value: str | None, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return default


def _rows(path: str | Path) -> Iterable[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        yield from csv.DictReader(fh)


def load_rvtools(
    vinfo: str | Path, vdisk: str | Path | None = None, vnetwork: str | Path | None = None
) -> list[VM]:
    vms: dict[str, VM] = {}
    for r in _rows(vinfo):
        name = (r.get("VM") or "").strip()
        if not name or _truthy(r.get("Template")):
            continue
        app = (r.get("Application") or r.get("Folder") or "").strip().strip("/").split("/")[-1]
        vms[name] = VM(
            name=name,
            guest_os=(
                r.get("OS according to the VMware Tools")
                or r.get("OS according to the configuration file")
                or ""
            ).strip(),
            cpus=_int(r.get("CPUs"), 1),
            memory_mb=_int(r.get("Memory"), 1024),
            power_state=(r.get("Powerstate") or "poweredOn").strip(),
            firmware=(r.get("Firmware") or "bios").strip().lower(),
            snapshots=_int(r.get("Snapshots")),
            tools_status=(r.get("Tools") or r.get("Tools Status") or "toolsOk").strip(),
            encrypted=_truthy(r.get("Encrypted")),
            datacenter=(r.get("Datacenter") or "").strip(),
            cluster=(r.get("Cluster") or "").strip(),
            host=(r.get("Host") or "").strip(),
            application=app,
            criticality=(r.get("Criticality") or "medium").strip().lower() or "medium",
            depends_on=[d.strip() for d in (r.get("Depends On") or "").split(";") if d.strip()],
        )
        if "Provisioned MiB" in r and not vdisk:
            vms[name].disks.append(Disk("disk-0", round(_int(r["Provisioned MiB"]) / 1024, 1)))

    if vdisk:
        for r in _rows(vdisk):
            vm = vms.get((r.get("VM") or "").strip())
            if vm is None:
                continue
            raw = _truthy(r.get("Raw"))
            vm.disks.append(
                Disk(
                    label=(r.get("Disk") or f"disk-{len(vm.disks)}").strip(),
                    capacity_gb=round(_int(r.get("Capacity MiB")) / 1024, 1),
                    datastore=(r.get("Path") or "").split("]")[0].strip("[ ") if r.get("Path") else "",
                    mode=(r.get("Disk Mode") or "persistent").strip(),
                    rdm=raw,
                    rdm_physical=raw and "physical" in (r.get("Raw Com. Mode") or "").lower(),
                    shared="multi" in (r.get("Sharing mode") or "").lower(),
                )
            )
    if vnetwork:
        for r in _rows(vnetwork):
            vm = vms.get((r.get("VM") or "").strip())
            if vm is not None:
                vm.nics.append(
                    Nic(
                        (r.get("Network") or "").strip(),
                        (r.get("IPv4 Address") or "").strip(),
                        (r.get("Mac Address") or "").strip(),
                    )
                )
    return list(vms.values())


def load_json(path: str | Path) -> list[VM]:
    return [VM.from_dict(item) for item in json.loads(Path(path).read_text(encoding="utf-8"))]


def to_json(vms: Iterable[VM]) -> str:
    return json.dumps([vm.to_dict() for vm in vms], indent=2)


def load_inventory(path: str | Path) -> list[VM]:
    """Load JSON, a single RVTools vInfo CSV, or a directory containing vInfo/vDisk/vNetwork CSVs."""
    path = Path(path)
    if path.is_dir():

        def find(tab: str) -> Path | None:
            hits = sorted(path.glob(f"*{tab}*.csv"))
            return hits[0] if hits else None

        vinfo = find("vInfo")
        if vinfo is None:
            raise FileNotFoundError(f"no *vInfo*.csv in {path}")
        return load_rvtools(vinfo, find("vDisk"), find("vNetwork"))
    if path.suffix.lower() == ".json":
        return load_json(path)
    return load_rvtools(path)


# ----------------------------------------------------------------------------- synthetic estate
_APPS = {
    "erp": ("high", ["erp-db", "erp-app", "erp-app", "erp-web"]),
    "crm": ("medium", ["crm-db", "crm-app", "crm-web"]),
    "hr-portal": ("low", ["hr-app", "hr-web"]),
    "file-services": ("medium", ["fileserver"]),
    "reporting": ("low", ["report-db", "report-etl"]),
    "payments": ("mission_critical", ["pay-db", "pay-api", "pay-api"]),
    "legacy-mainframe-gw": ("high", ["mfgw"]),
}
_OS = [
    "Red Hat Enterprise Linux 8 (64-bit)",
    "Red Hat Enterprise Linux 9 (64-bit)",
    "Microsoft Windows Server 2019 (64-bit)",
    "Microsoft Windows Server 2022 (64-bit)",
    "Ubuntu Linux (64-bit)",
    "CentOS 7 (64-bit)",
]


def sample_inventory(apps_multiplier: int = 1, seed: int | None = 42) -> list[VM]:
    """A small but realistic estate, including the edge cases the assessment must catch."""
    rng = random.Random(seed)
    vms: list[VM] = []
    for rep in range(apps_multiplier):
        for app, (crit, roles) in _APPS.items():
            suffix = f"-{rep + 1}" if apps_multiplier > 1 else ""
            names = []
            for i, role in enumerate(roles):
                name = f"{role}-{i + 1:02d}{suffix}"
                names.append(name)
                is_db = role.endswith("db")
                vm = VM(
                    name=name,
                    guest_os=rng.choice(_OS),
                    cpus=rng.choice([2, 4, 8, 16]) if not is_db else rng.choice([8, 16, 24]),
                    memory_mb=rng.choice([4096, 8192, 16384, 32768]) * (2 if is_db else 1),
                    firmware=rng.choice(["bios", "efi"]),
                    disks=[Disk("Hard disk 1", 80, "ds-gold-01")]
                    + ([Disk("Hard disk 2", rng.choice([250, 500, 1200]), "ds-gold-02")] if is_db else []),
                    nics=[
                        Nic(
                            "VM Network" if not is_db else "VLAN-120-DB",
                            f"10.20.{rng.randrange(1, 254)}.{rng.randrange(2, 254)}",
                        )
                    ],
                    snapshots=rng.choice([0, 0, 0, 1, 3]),
                    cluster="cl-prod-01",
                    host=f"esx{rng.randrange(1, 12):02d}.corp.local",
                    datacenter="dc-east",
                    application=app,
                    criticality=crit,
                )
                vms.append(vm)
            for name in names[1:]:  # app tiers depend on the first (database) tier
                next(v for v in vms if v.name == name).depends_on.append(names[0])

    # deliberate edge cases, injected into the first replica of each affected app
    def first(prefix: str) -> VM | None:
        return next((v for v in vms if v.name == prefix or v.name.startswith(prefix + "-")), None)

    if erp_db := first("erp-db-01"):
        erp_db.disks.append(Disk("Hard disk 3", 2048, "lun-erp", rdm=True, rdm_physical=True))
    if mfgw := first("mfgw-01"):
        mfgw.guest_os = "Microsoft Windows Server 2008 R2 (64-bit)"
        mfgw.passthrough_devices = 1
    if fileserver := first("fileserver-01"):
        fileserver.disks.append(Disk("Hard disk 2", 4096, "ds-bronze-01"))
        fileserver.tools_status = "toolsNotInstalled"
    return vms
