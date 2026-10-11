"""VMware vSphere → OpenShift Virtualization migration domain (assess → plan waves → MTV manifests)."""

from golden.migration.assessment import VMAssessment, assess_inventory, assess_vm
from golden.migration.inventory import VM, Disk, Nic, load_inventory, load_rvtools, sample_inventory
from golden.migration.manifests import MappingConfig, build_wave_manifests, write_wave_manifests
from golden.migration.waves import Wave, WavePlan, plan_waves

__all__ = [
    "VM",
    "Disk",
    "MappingConfig",
    "Nic",
    "VMAssessment",
    "Wave",
    "WavePlan",
    "assess_inventory",
    "assess_vm",
    "build_wave_manifests",
    "load_inventory",
    "load_rvtools",
    "plan_waves",
    "sample_inventory",
    "write_wave_manifests",
]
