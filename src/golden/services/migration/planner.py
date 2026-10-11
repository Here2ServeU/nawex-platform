"""Migration planner service — VMware inventory assessment, wave planning and MTV manifest generation."""

from __future__ import annotations

import os
from typing import Any

import yaml
from fastapi import HTTPException
from prometheus_client import Gauge
from pydantic import BaseModel, Field

from golden.migration import (
    VM,
    MappingConfig,
    assess_inventory,
    assess_vm,
    build_wave_manifests,
    plan_waves,
    sample_inventory,
)
from golden.services.common import create_app, run

SERVICE = "migration-planner"
VMS_BY_STATUS = Gauge("golden_migration_vms_total", "VMs by assessment status.", ["status"])
WAVES = Gauge("golden_migration_waves_planned", "Migration waves in the latest plan.")

app = create_app(SERVICE, "VMware vSphere → OpenShift Virtualization migration planning (MTV).")
MAX_VMS = 20_000


class InventoryIn(BaseModel):
    vms: list[dict[str, Any]] = Field(..., min_length=1, max_length=MAX_VMS)


class PlanIn(InventoryIn):
    max_vms_per_wave: int = Field(50, ge=1, le=1_000)
    max_tb_per_wave: float = Field(20.0, gt=0, le=1_000)
    pilot_size: int = Field(5, ge=1, le=100)


class ManifestIn(PlanIn):
    source_provider: str = Field("vsphere-prod", max_length=63)
    target_namespace: str = Field("migrated-vms", max_length=63)
    storage_class: str = Field("ocs-storagecluster-ceph-rbd-virtualization", max_length=253)


def _parse(vms: list[dict[str, Any]]) -> list[VM]:
    try:
        return [VM.from_dict(v) for v in vms]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid VM record: {exc}") from exc


@app.get("/api/v1/migration/sample-inventory")
def sample() -> dict:
    return {"vms": [vm.to_dict() for vm in sample_inventory()]}


@app.post("/api/v1/migration/assess")
def assess(body: InventoryIn) -> dict:
    result = assess_inventory(_parse(body.vms))
    for status in ("ready", "needs_remediation", "blocked"):
        VMS_BY_STATUS.labels(status=status).set(result["summary"][status])
    return result


@app.post("/api/v1/migration/plan")
def plan(body: PlanIn) -> dict:
    vms = _parse(body.vms)
    assessments = {vm.name: assess_vm(vm) for vm in vms}
    wave_plan = plan_waves(
        vms,
        max_vms_per_wave=body.max_vms_per_wave,
        max_tb_per_wave=body.max_tb_per_wave,
        pilot_size=body.pilot_size,
        assessments=assessments,
    )
    WAVES.set(len(wave_plan.waves))
    return wave_plan.to_dict()


@app.post("/api/v1/migration/manifests")
def manifests(body: ManifestIn) -> dict:
    vms = _parse(body.vms)
    wave_plan = plan_waves(
        vms,
        max_vms_per_wave=body.max_vms_per_wave,
        max_tb_per_wave=body.max_tb_per_wave,
        pilot_size=body.pilot_size,
    )
    cfg = MappingConfig(
        source_provider=body.source_provider,
        target_namespace=body.target_namespace,
        default_storage_class=body.storage_class,
    )
    return {
        "waves": [
            {
                "wave": w.name,
                "manifests": yaml.safe_dump_all(build_wave_manifests(w, vms, cfg), sort_keys=False),
            }
            for w in wave_plan.waves
        ],
        "backlog": wave_plan.backlog,
    }


def main() -> None:
    run(app, int(os.getenv("PORT", "8097")))


if __name__ == "__main__":
    main()
