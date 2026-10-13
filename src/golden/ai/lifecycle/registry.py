"""Model registry: versions, aliases (``champion`` / ``challenger`` / ``staging``), gated promotion, rollback.

Promotion to ``champion`` requires (a) the candidate passes every metric gate, (b) it is not worse than
the current champion beyond ``tolerance`` on the primary metric, and (c) a named human approver —
models that make decisions about money or patients are not promoted by a script alone. Rollback moves
the alias back to the previous champion; versions are immutable.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from golden.security.audit import default_audit_log


@dataclass
class ModelVersion:
    name: str
    version: int
    artifact: str
    metrics: dict[str, float]
    run_id: str = ""
    created: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PromotionRejected(RuntimeError):
    pass


class ModelRegistry:
    def __init__(self, root: str | Path = "models/registry") -> None:
        self.root = Path(root)

    # --- storage --------------------------------------------------------------------------------
    def _meta(self, name: str) -> Path:
        return self.root / name / "registry.json"

    def _load(self, name: str) -> dict[str, Any]:
        p = self._meta(name)
        return json.loads(p.read_text()) if p.exists() else {"versions": [], "aliases": {}, "history": []}

    def _save(self, name: str, data: dict[str, Any]) -> None:
        p = self._meta(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(p)

    # --- API ------------------------------------------------------------------------------------
    def register(
        self,
        name: str,
        artifact: str | Path,
        metrics: dict[str, float],
        *,
        run_id: str = "",
        alias: str | None = None,
    ) -> ModelVersion:
        data = self._load(name)
        version = len(data["versions"]) + 1
        dest = self.root / name / f"v{version}{Path(artifact).suffix}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(artifact, dest)
        mv = ModelVersion(name, version, str(dest), metrics, run_id)
        data["versions"].append(mv.to_dict())
        if alias:
            data["aliases"][alias] = version
        self._save(name, data)
        default_audit_log().record("model.register", {"model": name, "version": version, "metrics": metrics})
        return mv

    def get(self, name: str, ref: str | int) -> ModelVersion:
        data = self._load(name)
        version = data["aliases"].get(ref) if isinstance(ref, str) else ref
        if version is None or not 1 <= int(version) <= len(data["versions"]):
            raise KeyError(f"{name}@{ref} not found")
        return ModelVersion(**data["versions"][int(version) - 1])

    def aliases(self, name: str) -> dict[str, int]:
        return dict(self._load(name)["aliases"])

    def versions(self, name: str) -> list[ModelVersion]:
        return [ModelVersion(**v) for v in self._load(name)["versions"]]

    def set_alias(self, name: str, alias: str, version: int) -> None:
        data = self._load(name)
        data["aliases"][alias] = version
        self._save(name, data)

    def promote(
        self,
        name: str,
        version: int,
        *,
        gates: dict[str, float],
        primary_metric: str,
        approver: str = "",
        tolerance: float = 0.0,
        higher_is_better: frozenset[str] = frozenset({"recall", "precision", "f1", "auc", "accuracy"}),
    ) -> dict[str, Any]:
        candidate = self.get(name, version)
        failures = []
        for metric, threshold in gates.items():
            value = candidate.metrics.get(metric)
            ok = value is not None and (
                value >= threshold if metric in higher_is_better else value <= threshold
            )
            if not ok:
                failures.append(f"{metric}={value} fails gate {threshold}")
        data = self._load(name)
        current = data["aliases"].get("champion")
        if current and current != version:
            champ = self.get(name, current).metrics.get(primary_metric, 0.0)
            if candidate.metrics.get(primary_metric, 0.0) < champ - tolerance:
                failures.append(
                    f"{primary_metric} {candidate.metrics.get(primary_metric)} < champion {champ}"
                )
        if not approver or len(approver.strip()) < 3:
            failures.append("champion promotion requires a named human approver")
        if failures:
            default_audit_log().record(
                "model.promote.rejected", {"model": name, "version": version, "failures": failures}
            )
            raise PromotionRejected("; ".join(failures))
        data["history"].append(
            {"from": current, "to": version, "approver": approver, "ts": datetime.now(UTC).isoformat()}
        )
        data["aliases"]["champion"] = version
        if data["aliases"].get("challenger") == version:
            data["aliases"].pop("challenger")
        self._save(name, data)
        default_audit_log().record(
            "model.promote", {"model": name, "from": current, "to": version}, actor=approver
        )
        return {"model": name, "champion": version, "previous": current}

    def rollback(self, name: str, *, approver: str) -> dict[str, Any]:
        data = self._load(name)
        if not data["history"]:
            raise PromotionRejected("no promotion history to roll back")
        last = data["history"].pop()
        if last["from"] is None:
            raise PromotionRejected("no previous champion")
        data["aliases"]["champion"] = last["from"]
        self._save(name, data)
        default_audit_log().record("model.rollback", {"model": name, "to": last["from"]}, actor=approver)
        return {"model": name, "champion": last["from"], "rolled_back_from": last["to"]}
