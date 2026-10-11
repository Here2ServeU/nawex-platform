"""Generate Migration Toolkit for Virtualization (MTV / Forklift) custom resources per wave.

Output per wave: ``NetworkMap``, ``StorageMap``, ``Plan`` and ``Migration`` (``forklift.konveyor.io/v1beta1``)
plus a ``kustomization.yaml``, ready for GitOps (Argo CD) or ``oc apply -k``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from golden.migration.inventory import VM
from golden.migration.waves import Wave

API = "forklift.konveyor.io/v1beta1"


@dataclass
class MappingConfig:
    mtv_namespace: str = "openshift-mtv"
    source_provider: str = "vsphere-prod"
    destination_provider: str = "host"
    target_namespace: str = "migrated-vms"
    default_storage_class: str = "ocs-storagecluster-ceph-rbd-virtualization"
    storage_classes: dict[str, str] = field(default_factory=dict)  # datastore -> storage class
    pod_networks: tuple[str, ...] = ("VM Network",)  # vSphere networks mapped to the pod network
    nad_namespace: str = "migrated-vms"  # Multus NADs named after the sanitized vSphere network


def k8s_name(value: str) -> str:
    name = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return (name or "x")[:63].rstrip("-")


def _meta(name: str, cfg: MappingConfig, wave: Wave) -> dict[str, Any]:
    return {
        "name": name,
        "namespace": cfg.mtv_namespace,
        "labels": {"app.kubernetes.io/part-of": "golden-platform", "golden.io/wave": wave.name},
    }


def _provider_refs(cfg: MappingConfig) -> dict[str, Any]:
    return {
        "source": {"name": cfg.source_provider, "namespace": cfg.mtv_namespace},
        "destination": {"name": cfg.destination_provider, "namespace": cfg.mtv_namespace},
    }


def build_wave_manifests(
    wave: Wave, vms: Sequence[VM], cfg: MappingConfig | None = None
) -> list[dict[str, Any]]:
    cfg = cfg or MappingConfig()
    members = [vm for vm in vms if vm.name in set(wave.vms)]
    networks = sorted({n.network for vm in members for n in vm.nics if n.network})
    datastores = sorted({d.datastore for vm in members for d in vm.disks if d.datastore})
    base = k8s_name(wave.name)

    network_map = {
        "apiVersion": API,
        "kind": "NetworkMap",
        "metadata": _meta(f"{base}-network", cfg, wave),
        "spec": {
            "provider": _provider_refs(cfg),
            "map": [
                {
                    "source": {"name": net},
                    "destination": {"type": "pod"}
                    if net in cfg.pod_networks
                    else {"type": "multus", "name": k8s_name(net), "namespace": cfg.nad_namespace},
                }
                for net in networks
            ],
        },
    }
    storage_map = {
        "apiVersion": API,
        "kind": "StorageMap",
        "metadata": _meta(f"{base}-storage", cfg, wave),
        "spec": {
            "provider": _provider_refs(cfg),
            "map": [
                {
                    "source": {"name": ds},
                    "destination": {"storageClass": cfg.storage_classes.get(ds, cfg.default_storage_class)},
                }
                for ds in datastores
            ],
        },
    }
    plan = {
        "apiVersion": API,
        "kind": "Plan",
        "metadata": _meta(base, cfg, wave),
        "spec": {
            "warm": wave.warm,
            "targetNamespace": cfg.target_namespace,
            "provider": _provider_refs(cfg),
            "map": {
                "network": {"name": f"{base}-network", "namespace": cfg.mtv_namespace},
                "storage": {"name": f"{base}-storage", "namespace": cfg.mtv_namespace},
            },
            "vms": [{"name": name} for name in sorted(wave.vms)],
        },
    }
    migration = {
        "apiVersion": API,
        "kind": "Migration",
        "metadata": _meta(f"{base}-run", cfg, wave),
        "spec": {"plan": {"name": base, "namespace": cfg.mtv_namespace}},
    }
    return [network_map, storage_map, plan, migration]


def write_wave_manifests(
    out_dir: str | Path, waves: Sequence[Wave], vms: Sequence[VM], cfg: MappingConfig | None = None
) -> list[Path]:
    """Write ``<out_dir>/<wave>/{networkmap,storagemap,plan,migration}.yaml`` + kustomizations."""
    out = Path(out_dir)
    written: list[Path] = []
    for wave in waves:
        wave_dir = out / k8s_name(wave.name)
        wave_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for doc in build_wave_manifests(wave, vms, cfg):
            path = wave_dir / f"{doc['kind'].lower()}.yaml"
            path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            files.append(path.name)
            written.append(path)
        kustomization = wave_dir / "kustomization.yaml"
        kustomization.write_text(
            yaml.safe_dump(
                {
                    "apiVersion": "kustomize.config.k8s.io/v1beta1",
                    "kind": "Kustomization",
                    "resources": files,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        written.append(kustomization)
    return written
