"""Persona-based access model (``security/identity/access-model.yaml``) — loader and linter.

The same file drives Terraform (``deploy/terraform/modules/aws/identity-center``), so linting it here
catches design mistakes before a plan: privileged policies on everyday personas, over-long sessions,
delegated IAM without a permission boundary, AD groups that break the naming convention, and
assignments into the management account.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = "security/identity/access-model.yaml"
PERMISSION_SET_NAME = re.compile(r"^[\w+=,.@-]{1,32}$")
SESSION = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?$")
# Policies that grant (or can grant themselves) administrator access.
PRIVILEGED_POLICIES = frozenset({"AdministratorAccess", "IAMFullAccess"})
# Broad policies acceptable only behind a permission boundary.
BOUNDARY_REQUIRED_POLICIES = frozenset({"PowerUserAccess"})


@dataclass
class Assignment:
    group: str
    account_groups: list[str]


@dataclass
class Persona:
    name: str
    permission_set: str
    description: str = ""
    session_duration: str = "PT8H"
    aws_managed_policies: list[str] = field(default_factory=list)
    customer_managed_policies: list[str] = field(default_factory=list)
    inline_policy: list[dict[str, Any]] = field(default_factory=list)
    permissions_boundary: bool = False
    delegated_iam: bool = False
    privileged: bool = False
    allow_management: bool = False
    relay_state: str = ""
    assignments: list[Assignment] = field(default_factory=list)

    @property
    def session_hours(self) -> float:
        return session_hours(self.session_duration)

    @property
    def groups(self) -> list[str]:
        return sorted({a.group for a in self.assignments})

    @property
    def policy_names(self) -> set[str]:
        return {p.rsplit("/", 1)[-1] for p in self.aws_managed_policies}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AccessModel:
    personas: list[Persona]
    permission_boundary: str
    identity_source: dict[str, Any] = field(default_factory=dict)
    account_groups: list[str] = field(default_factory=list)
    max_session_hours: float = 8
    max_privileged_session_hours: float = 1

    @property
    def group_pattern(self) -> str:
        return str(self.identity_source.get("group_pattern", r"^AWS-[A-Za-z0-9-]+$"))

    def persona(self, name: str) -> Persona | None:
        return next((p for p in self.personas if name in (p.name, p.permission_set)), None)

    def group_map(self) -> dict[str, list[dict[str, Any]]]:
        """AD group → what it grants (permission set × account groups)."""
        out: dict[str, list[dict[str, Any]]] = {}
        for p in self.personas:
            for a in p.assignments:
                out.setdefault(a.group, []).append(
                    {
                        "persona": p.name,
                        "permission_set": p.permission_set,
                        "account_groups": a.account_groups,
                    }
                )
        return dict(sorted(out.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "permission_boundary": self.permission_boundary,
            "identity_source": self.identity_source,
            "account_groups": self.account_groups,
            "personas": [p.to_dict() for p in self.personas],
            "group_map": self.group_map(),
        }


@dataclass
class ModelFinding:
    code: str
    severity: str  # error | warning
    persona: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def session_hours(duration: str) -> float:
    match = SESSION.match(duration or "")
    if not match or not any(match.groups()):
        raise ValueError(f"invalid ISO-8601 session duration {duration!r} (expected e.g. PT4H, PT1H30M)")
    hours, minutes = (int(g) if g else 0 for g in match.groups())
    return hours + minutes / 60


def parse_model(data: dict[str, Any]) -> AccessModel:
    if not isinstance(data, dict) or not data.get("personas"):
        raise ValueError("access model must define a non-empty 'personas' list")
    personas = []
    for raw in data["personas"]:
        raw = dict(raw)
        raw["assignments"] = [Assignment(**a) for a in raw.get("assignments", [])]
        personas.append(Persona(**raw))
    limits = data.get("limits", {})
    return AccessModel(
        personas=personas,
        permission_boundary=str(data.get("permission_boundary", "")),
        identity_source=dict(data.get("identity_source", {})),
        account_groups=list(data.get("account_groups", [])),
        max_session_hours=float(limits.get("max_session_hours", 8)),
        max_privileged_session_hours=float(limits.get("max_privileged_session_hours", 1)),
    )


def model_path(path: str | Path | None = None) -> Path:
    return Path(path or os.getenv("GOLDEN_ACCESS_MODEL") or DEFAULT_PATH)


def load_model(path: str | Path | None = None) -> AccessModel:
    target = model_path(path)
    if not target.exists():
        raise FileNotFoundError(f"access model not found at {target} (set GOLDEN_ACCESS_MODEL)")
    return parse_model(yaml.safe_load(target.read_text(encoding="utf-8")))


def lint_model(model: AccessModel) -> list[ModelFinding]:
    findings: list[ModelFinding] = []

    def add(code: str, severity: str, persona: str, message: str) -> None:
        findings.append(ModelFinding(code, severity, persona, message))

    if not model.permission_boundary:
        add("NO_BOUNDARY_POLICY", "error", "*", "permission_boundary is not set")
    group_re = re.compile(model.group_pattern)
    seen: dict[str, str] = {}
    for p in model.personas:
        if p.permission_set in seen:
            add(
                "DUPLICATE_PERMISSION_SET",
                "error",
                p.name,
                f"{p.permission_set} also used by {seen[p.permission_set]}",
            )
        seen[p.permission_set] = p.name
        if not PERMISSION_SET_NAME.match(p.permission_set):
            add(
                "INVALID_NAME",
                "error",
                p.name,
                f"{p.permission_set!r} is not a valid permission set name (≤32 chars)",
            )

        try:
            hours = p.session_hours
        except ValueError as exc:
            add("INVALID_SESSION", "error", p.name, str(exc))
            hours = 0
        if hours > model.max_session_hours:
            add(
                "SESSION_TOO_LONG",
                "error",
                p.name,
                f"{p.session_duration} exceeds {model.max_session_hours:g}h",
            )
        if p.privileged and hours > model.max_privileged_session_hours:
            add(
                "PRIVILEGED_SESSION_TOO_LONG",
                "error",
                p.name,
                f"privileged sessions are limited to {model.max_privileged_session_hours:g}h",
            )

        privileged_policies = p.policy_names & PRIVILEGED_POLICIES
        if privileged_policies and not p.privileged:
            add(
                "PRIVILEGED_POLICY",
                "error",
                p.name,
                f"{', '.join(sorted(privileged_policies))} on a non-privileged persona; use the break-glass persona",
            )
        if p.policy_names & BOUNDARY_REQUIRED_POLICIES and not p.permissions_boundary:
            add(
                "BROAD_POLICY_WITHOUT_BOUNDARY",
                "error",
                p.name,
                "PowerUserAccess requires permissions_boundary: true",
            )
        if p.delegated_iam and not p.permissions_boundary:
            add(
                "DELEGATED_IAM_WITHOUT_BOUNDARY",
                "error",
                p.name,
                "delegated_iam requires permissions_boundary: true",
            )
        for stmt in p.inline_policy:
            actions = stmt.get("Action", [])
            actions = [actions] if isinstance(actions, str) else actions
            if stmt.get("Effect") == "Allow" and ("*" in actions or stmt.get("NotAction")):
                add("WILDCARD_INLINE", "error", p.name, f"inline statement {stmt.get('Sid', '?')} allows '*'")

        if not p.assignments:
            add("UNASSIGNED", "warning", p.name, "persona has no group assignments")
        for a in p.assignments:
            if not group_re.match(a.group):
                add(
                    "GROUP_NAMING",
                    "error",
                    p.name,
                    f"AD group {a.group!r} does not match {model.group_pattern}",
                )
            unknown = set(a.account_groups) - set(model.account_groups) if model.account_groups else set()
            if unknown:
                add("UNKNOWN_ACCOUNT_GROUP", "error", p.name, f"unknown account groups {sorted(unknown)}")
            if "management" in a.account_groups and not p.allow_management:
                add(
                    "MANAGEMENT_ACCOUNT_ACCESS",
                    "error",
                    p.name,
                    "assignment to the management account needs allow_management: true",
                )
    return findings


def lint_summary(model: AccessModel) -> dict[str, Any]:
    findings = lint_model(model)
    return {
        "valid": not any(f.severity == "error" for f in findings),
        "personas": len(model.personas),
        "groups": len(model.group_map()),
        "privileged_personas": [p.name for p in model.personas if p.privileged],
        "findings": [f.to_dict() for f in findings],
    }
