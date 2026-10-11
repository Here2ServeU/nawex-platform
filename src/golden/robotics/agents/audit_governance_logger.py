"""Governance trail for autonomous robotic interventions, backed by the tamper-evident audit chain."""

from __future__ import annotations

from typing import Any

from golden.security.audit import AuditLog


class AuditGovernanceLogger:
    def __init__(self, path: str | None = None) -> None:
        self.audit = AuditLog(path)

    def log_incident(self, incident_report: dict[str, Any]) -> str:
        entry = self.audit.record(
            "robotics.autonomous_intervention", incident_report, actor="safety-interceptor"
        )
        return entry.hash

    def verify(self) -> bool:
        return self.audit.verify()
