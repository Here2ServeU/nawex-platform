"""Wave planning: group VMs into move groups that respect application dependencies.

1. Union VMs that share an application or a dependency edge (move groups must migrate together).
2. Drop groups containing a *blocked* VM (they go to the remediation backlog).
3. Order groups: pilot first (lowest criticality × complexity), mission-critical last.
4. Pack groups into waves bounded by ``max_vms_per_wave`` and ``max_tb_per_wave``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from golden.migration.assessment import VMAssessment, assess_vm
from golden.migration.inventory import VM

_CRIT_RANK = {"low": 0, "medium": 1, "high": 2, "mission_critical": 3}


@dataclass
class Wave:
    name: str
    index: int
    vms: list[str] = field(default_factory=list)
    applications: list[str] = field(default_factory=list)
    total_disk_gb: float = 0.0
    estimated_hours: float = 0.0
    warm: bool = False
    pilot: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WavePlan:
    waves: list[Wave]
    backlog: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"waves": [w.to_dict() for w in self.waves], "backlog": self.backlog}


class _DSU:
    def __init__(self, items: Sequence[str]) -> None:
        self.parent = {i: i for i in items}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        if a in self.parent and b in self.parent:
            self.parent[self.find(a)] = self.find(b)


def plan_waves(
    vms: Sequence[VM],
    *,
    max_vms_per_wave: int = 50,
    max_tb_per_wave: float = 20.0,
    pilot_size: int = 5,
    assessments: dict[str, VMAssessment] | None = None,
) -> WavePlan:
    assessments = assessments or {vm.name: assess_vm(vm) for vm in vms}
    by_name = {vm.name: vm for vm in vms}
    dsu = _DSU(list(by_name))
    first_in_app: dict[str, str] = {}
    for vm in vms:
        if vm.application:
            dsu.union(vm.name, first_in_app.setdefault(vm.application, vm.name))
        for dep in vm.depends_on:
            dsu.union(vm.name, dep)

    groups: dict[str, list[VM]] = {}
    for vm in vms:
        groups.setdefault(dsu.find(vm.name), []).append(vm)

    ready_groups, backlog = [], []
    for members in groups.values():
        blocked = [m.name for m in members if assessments[m.name].readiness == "blocked"]
        apps = sorted({m.application or "unassigned" for m in members})
        if blocked:
            backlog.append(
                {"applications": apps, "vms": sorted(m.name for m in members), "blocked_by": blocked}
            )
        else:
            ready_groups.append(members)

    def score(members: list[VM]) -> tuple[int, int, int]:
        crit = max(_CRIT_RANK.get(m.criticality, 1) for m in members)
        complexity = sum(assessments[m.name].complexity for m in members)
        return crit, complexity, len(members)

    ready_groups.sort(key=score)
    waves: list[Wave] = []
    current: Wave | None = None
    for members in ready_groups:
        size_gb = sum(m.total_disk_gb for m in members)
        is_pilot = not waves and len(members) <= pilot_size
        needs_new = (
            current is None
            or current.pilot
            or len(current.vms) + len(members) > max_vms_per_wave
            or (current.total_disk_gb + size_gb) / 1024 > max_tb_per_wave
        )
        if needs_new:
            current = Wave(name=f"wave-{len(waves):02d}", index=len(waves), pilot=is_pilot)
            waves.append(current)
        assert current is not None
        current.vms.extend(sorted(m.name for m in members))
        current.applications = sorted(
            set(current.applications) | {m.application or "unassigned" for m in members}
        )
        current.total_disk_gb = round(current.total_disk_gb + size_gb, 1)
        current.estimated_hours = round(
            current.estimated_hours + sum(assessments[m.name].estimated_hours for m in members), 2
        )
        current.warm = current.warm or any(assessments[m.name].migration_type == "warm" for m in members)
    return WavePlan(waves, backlog)
