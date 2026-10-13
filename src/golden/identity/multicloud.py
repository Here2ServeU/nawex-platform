"""Azure and GCP persona access models — loader, linter and the cross-cloud persona matrix.

``security/identity/azure-access-model.yaml`` and ``security/identity/gcp-access-model.yaml`` are the
Azure and GCP twins of the AWS ``access-model.yaml`` (:mod:`golden.identity.model`). The same files drive
Terraform (``deploy/terraform/modules/azure/governance`` and ``deploy/terraform/modules/gcp/org-governance``),
so linting them here catches design mistakes before a plan. The rules follow the AWS linter in spirit:

* privileged roles (Owner, ``roles/owner`` …) only on the break-glass persona;
* privileged personas are never standing — PIM-eligible (Azure) or a PAM entitlement (GCP), approval-gated,
  with a short activation window;
* just-in-time activation windows bounded by the model's limits;
* broad roles (Contributor, ``roles/editor``) never standing in production;
* group names follow the directory naming convention; scopes are known; the hierarchy root
  (Azure root management group, GCP organization node) needs an explicit opt-in.

:func:`persona_matrix` lines the three clouds up persona by persona (AWS permission set ↔ Azure role ↔ GCP
role) and flags personas defined in one cloud but missing in another, or privileged in one and not another.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from golden.identity.model import AccessModel, load_model, session_hours

AZURE_DEFAULT_PATH = "security/identity/azure-access-model.yaml"
GCP_DEFAULT_PATH = "security/identity/gcp-access-model.yaml"
CLOUDS = ("aws", "azure", "gcp")
GCP_ROLE = re.compile(r"^(roles/[A-Za-z0-9_.]+|(organizations|projects)/[^/]+/roles/[A-Za-z0-9_.]+)$")


@dataclass(frozen=True)
class CloudRules:
    """Cloud-specific vocabulary for the shared lint rules."""

    cloud: str
    standing: str  # assignment value meaning "always on"
    jit: str  # assignment value meaning "just-in-time"
    duration_key: str  # YAML key holding the JIT window
    top_scope: str  # hierarchy root
    top_flag: str  # persona flag that allows the hierarchy root
    max_key: str
    max_privileged_key: str
    privileged_roles: frozenset[str]
    broad_roles: frozenset[str]
    prod_scopes: frozenset[str]
    basic_roles: frozenset[str] = frozenset()


AZURE = CloudRules(
    cloud="azure",
    standing="active",
    jit="eligible",
    duration_key="activation_duration",
    top_scope="root",
    top_flag="allow_root",
    max_key="max_activation_hours",
    max_privileged_key="max_privileged_activation_hours",
    # Roles that can grant themselves (or anyone) any access.
    privileged_roles=frozenset(
        {"Owner", "User Access Administrator", "Role Based Access Control Administrator"}
    ),
    broad_roles=frozenset({"Contributor"}),
    prod_scopes=frozenset({"landing-zones-prod"}),
)

GCP = CloudRules(
    cloud="gcp",
    standing="binding",
    jit="entitlement",
    duration_key="max_request_duration",
    top_scope="organization",
    top_flag="allow_organization",
    max_key="max_request_hours",
    max_privileged_key="max_privileged_request_hours",
    privileged_roles=frozenset(
        {
            "roles/owner",
            "roles/resourcemanager.organizationAdmin",
            "roles/resourcemanager.folderAdmin",
            "roles/iam.securityAdmin",
            "roles/iam.organizationRoleAdmin",
            "roles/orgpolicy.policyAdmin",
        }
    ),
    broad_roles=frozenset({"roles/editor"}),
    prod_scopes=frozenset({"landing-zones-prod"}),
    basic_roles=frozenset({"roles/editor", "roles/owner"}),
)

RULES = {"azure": AZURE, "gcp": GCP}


@dataclass
class CloudAssignment:
    group: str
    scopes: list[str]


@dataclass
class CloudPersona:
    name: str
    roles: list[str]
    assignment: str
    description: str = ""
    duration: str = ""  # activation_duration (Azure) / max_request_duration (GCP)
    require_approval: bool = False
    privileged: bool = False
    allow_top: bool = False  # allow_root (Azure) / allow_organization (GCP)
    assignments: list[CloudAssignment] = field(default_factory=list)

    @property
    def groups(self) -> list[str]:
        return sorted({a.group for a in self.assignments})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CloudAccessModel:
    cloud: str
    personas: list[CloudPersona]
    identity_source: dict[str, Any] = field(default_factory=dict)
    scopes: list[str] = field(default_factory=list)
    max_hours: float = 8
    max_privileged_hours: float = 1

    @property
    def rules(self) -> CloudRules:
        return RULES[self.cloud]

    @property
    def group_pattern(self) -> str:
        default = r"^AZ-[A-Za-z0-9-]+$" if self.cloud == "azure" else r"^gcp-[a-z0-9-]+@[a-z0-9.-]+$"
        return str(self.identity_source.get("group_pattern", default))

    def persona(self, name: str) -> CloudPersona | None:
        return next((p for p in self.personas if p.name == name), None)

    def group_map(self) -> dict[str, list[dict[str, Any]]]:
        """Directory group → what it grants (roles × scopes)."""
        out: dict[str, list[dict[str, Any]]] = {}
        for p in self.personas:
            for a in p.assignments:
                out.setdefault(a.group, []).append(
                    {"persona": p.name, "roles": p.roles, "assignment": p.assignment, "scopes": a.scopes}
                )
        return dict(sorted(out.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "cloud": self.cloud,
            "identity_source": self.identity_source,
            "scopes": self.scopes,
            "personas": [p.to_dict() for p in self.personas],
            "group_map": self.group_map(),
        }


@dataclass
class CloudFinding:
    code: str
    severity: str  # error | warning
    cloud: str
    persona: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


# ----------------------------------------------------------------------------------------- parsing
def _expand(group: str, identity_source: dict[str, Any]) -> str:
    domain = str(identity_source.get("domain", ""))
    return group.replace("${domain}", domain) if domain else group


def parse_cloud_model(data: dict[str, Any], cloud: str) -> CloudAccessModel:
    if cloud not in RULES:
        raise ValueError(f"unknown cloud {cloud!r} (expected one of {sorted(RULES)})")
    if not isinstance(data, dict) or not data.get("personas"):
        raise ValueError(f"{cloud} access model must define a non-empty 'personas' list")
    rules = RULES[cloud]
    identity_source = dict(data.get("identity_source", {}))
    personas = []
    for raw in data["personas"]:
        if not isinstance(raw, dict) or "name" not in raw:
            raise ValueError(f"{cloud} persona entries must be mappings with a 'name'")
        roles = raw.get("roles", [])
        personas.append(
            CloudPersona(
                name=str(raw["name"]),
                roles=[roles] if isinstance(roles, str) else [str(r) for r in roles],
                assignment=str(raw.get("assignment", rules.standing)),
                description=str(raw.get("description", "")),
                duration=str(raw.get(rules.duration_key, "") or ""),
                require_approval=bool(raw.get("require_approval", False)),
                privileged=bool(raw.get("privileged", False)),
                allow_top=bool(raw.get(rules.top_flag, False)),
                assignments=[
                    CloudAssignment(
                        group=_expand(str(a["group"]), identity_source), scopes=list(a.get("scopes", []))
                    )
                    for a in raw.get("assignments", [])
                ],
            )
        )
    limits = data.get("limits", {}) or {}
    return CloudAccessModel(
        cloud=cloud,
        personas=personas,
        identity_source=identity_source,
        scopes=[str(s) for s in data.get("scopes", [])],
        max_hours=float(limits.get(rules.max_key, 8)),
        max_privileged_hours=float(limits.get(rules.max_privileged_key, 1)),
    )


def cloud_model_path(cloud: str, path: str | Path | None = None) -> Path:
    if cloud == "azure":
        return Path(path or os.getenv("GOLDEN_AZURE_ACCESS_MODEL") or AZURE_DEFAULT_PATH)
    if cloud == "gcp":
        return Path(path or os.getenv("GOLDEN_GCP_ACCESS_MODEL") or GCP_DEFAULT_PATH)
    raise ValueError(f"unknown cloud {cloud!r}")


def load_cloud_model(cloud: str, path: str | Path | None = None) -> CloudAccessModel:
    target = cloud_model_path(cloud, path)
    if not target.exists():
        env = "GOLDEN_AZURE_ACCESS_MODEL" if cloud == "azure" else "GOLDEN_GCP_ACCESS_MODEL"
        raise FileNotFoundError(f"{cloud} access model not found at {target} (set {env})")
    return parse_cloud_model(yaml.safe_load(target.read_text(encoding="utf-8")), cloud)


# ----------------------------------------------------------------------------------------- linting
def lint_cloud_model(model: CloudAccessModel) -> list[CloudFinding]:
    rules = model.rules
    findings: list[CloudFinding] = []

    def add(code: str, severity: str, persona: str, message: str) -> None:
        findings.append(CloudFinding(code, severity, model.cloud, persona, message))

    try:
        group_re = re.compile(model.group_pattern)
    except re.error as exc:
        add("INVALID_GROUP_PATTERN", "error", "*", f"group_pattern does not compile: {exc}")
        group_re = re.compile(r".*")
    seen: set[str] = set()
    for p in model.personas:
        if p.name in seen:
            add("DUPLICATE_PERSONA", "error", p.name, "persona name is defined twice")
        seen.add(p.name)

        if not p.roles:
            add("NO_ROLES", "error", p.name, "persona grants no roles")
        if model.cloud == "gcp":
            for role in p.roles:
                if not GCP_ROLE.match(role):
                    add(
                        "INVALID_ROLE",
                        "error",
                        p.name,
                        f"{role!r} is not a GCP role name (roles/... or custom)",
                    )

        if p.assignment not in (rules.standing, rules.jit):
            add(
                "INVALID_ASSIGNMENT_TYPE",
                "error",
                p.name,
                f"assignment {p.assignment!r} must be {rules.standing!r} or {rules.jit!r}",
            )
        jit = p.assignment == rules.jit

        privileged_roles = set(p.roles) & rules.privileged_roles
        if privileged_roles and not p.privileged:
            add(
                "PRIVILEGED_ROLE",
                "error",
                p.name,
                f"{', '.join(sorted(privileged_roles))} on a non-privileged persona; use the break-glass persona",
            )
        if p.privileged and not jit:
            add(
                "STANDING_PRIVILEGE",
                "error",
                p.name,
                f"privileged personas must be just-in-time (assignment: {rules.jit})",
            )
        if p.privileged and not p.require_approval:
            add(
                "PRIVILEGED_WITHOUT_APPROVAL",
                "error",
                p.name,
                "privileged activation must set require_approval",
            )

        hours = 0.0
        if jit:
            if not p.duration:
                add("MISSING_DURATION", "error", p.name, f"{rules.jit} assignments need {rules.duration_key}")
            else:
                try:
                    hours = session_hours(p.duration)
                except ValueError as exc:
                    add("INVALID_DURATION", "error", p.name, str(exc))
        elif p.duration:
            add(
                "DURATION_IGNORED",
                "warning",
                p.name,
                f"{rules.duration_key} only applies to {rules.jit} assignments",
            )
        if hours > model.max_hours:
            add("ACTIVATION_TOO_LONG", "error", p.name, f"{p.duration} exceeds {model.max_hours:g}h")
        if p.privileged and hours > model.max_privileged_hours:
            add(
                "PRIVILEGED_ACTIVATION_TOO_LONG",
                "error",
                p.name,
                f"privileged activation is limited to {model.max_privileged_hours:g}h",
            )

        basic = (set(p.roles) & rules.basic_roles) - rules.privileged_roles
        if basic:
            add("BASIC_ROLE", "warning", p.name, f"basic role(s) {sorted(basic)}; prefer predefined roles")

        if not p.assignments:
            add("UNASSIGNED", "warning", p.name, "persona has no group assignments")
        broad = set(p.roles) & rules.broad_roles
        for a in p.assignments:
            if not group_re.match(a.group):
                add(
                    "GROUP_NAMING", "error", p.name, f"group {a.group!r} does not match {model.group_pattern}"
                )
            if not a.scopes:
                add("NO_SCOPES", "error", p.name, f"assignment for {a.group} has no scopes")
            unknown = set(a.scopes) - set(model.scopes) if model.scopes else set()
            if unknown:
                add("UNKNOWN_SCOPE", "error", p.name, f"unknown scopes {sorted(unknown)}")
            if rules.top_scope in a.scopes and not p.allow_top:
                add(
                    "ROOT_SCOPE_ACCESS",
                    "error",
                    p.name,
                    f"assignment at {rules.top_scope!r} needs {rules.top_flag}: true",
                )
            if broad and not jit and set(a.scopes) & rules.prod_scopes:
                add(
                    "STANDING_BROAD_ROLE_IN_PROD",
                    "error",
                    p.name,
                    f"{', '.join(sorted(broad))} in production must be {rules.jit}, not {rules.standing}",
                )
    return findings


def lint_cloud_summary(model: CloudAccessModel) -> dict[str, Any]:
    findings = lint_cloud_model(model)
    return {
        "cloud": model.cloud,
        "valid": not any(f.severity == "error" for f in findings),
        "personas": len(model.personas),
        "groups": len(model.group_map()),
        "privileged_personas": [p.name for p in model.personas if p.privileged],
        "findings": [f.to_dict() for f in findings],
    }


# ---------------------------------------------------------------------------- cross-cloud matrix
def _aws_cell(model: AccessModel, name: str) -> dict[str, Any] | None:
    p = model.persona(name)
    if p is None or p.name != name:
        return None
    return {
        "permission_set": p.permission_set,
        "policies": sorted(p.aws_managed_policies) + sorted(p.customer_managed_policies),
        "privileged": p.privileged,
        "groups": p.groups,
    }


def _cloud_cell(model: CloudAccessModel, name: str) -> dict[str, Any] | None:
    p = model.persona(name)
    if p is None:
        return None
    return {
        "roles": p.roles,
        "assignment": p.assignment,
        "privileged": p.privileged,
        "groups": p.groups,
    }


def persona_matrix(
    aws: AccessModel | None = None,
    azure: CloudAccessModel | None = None,
    gcp: CloudAccessModel | None = None,
) -> dict[str, Any]:
    """Persona → AWS permission set / Azure roles / GCP roles, with gaps between clouds flagged.

    Only the clouds passed in are compared; a persona present in any of them but absent from another is
    reported as ``PERSONA_MISSING``; a persona privileged in one cloud but not another as
    ``PRIVILEGE_MISMATCH`` (break-glass must mean the same thing everywhere).
    """
    present: dict[str, set[str]] = {}
    if aws is not None:
        present["aws"] = {p.name for p in aws.personas}
    if azure is not None:
        present["azure"] = {p.name for p in azure.personas}
    if gcp is not None:
        present["gcp"] = {p.name for p in gcp.personas}
    names = sorted(set().union(*present.values())) if present else []

    rows: list[dict[str, Any]] = []
    findings: list[CloudFinding] = []
    for name in names:
        cells: dict[str, dict[str, Any] | None] = {}
        if aws is not None:
            cells["aws"] = _aws_cell(aws, name)
        if azure is not None:
            cells["azure"] = _cloud_cell(azure, name)
        if gcp is not None:
            cells["gcp"] = _cloud_cell(gcp, name)
        missing = [c for c in CLOUDS if c in cells and cells[c] is None]
        for cloud in missing:
            defined = [c for c in CLOUDS if c in cells and cells[c] is not None]
            findings.append(
                CloudFinding(
                    "PERSONA_MISSING",
                    "warning",
                    cloud,
                    name,
                    f"defined in {', '.join(defined)} but not in {cloud}",
                )
            )
        privileged = {c: bool(cell["privileged"]) for c, cell in cells.items() if cell is not None}
        mismatch = len(set(privileged.values())) > 1
        if mismatch:
            findings.append(
                CloudFinding(
                    "PRIVILEGE_MISMATCH",
                    "error",
                    ",".join(sorted(privileged)),
                    name,
                    "privileged in " + ", ".join(sorted(c for c, v in privileged.items() if v)) + " only",
                )
            )
        rows.append({"persona": name, **cells, "missing": missing, "privilege_mismatch": mismatch})

    return {
        "clouds": [c for c in CLOUDS if c in present],
        "personas": rows,
        "consistent": not findings,
        "findings": [f.to_dict() for f in findings],
    }


def load_all(
    aws_path: str | Path | None = None,
    azure_path: str | Path | None = None,
    gcp_path: str | Path | None = None,
) -> tuple[AccessModel, CloudAccessModel, CloudAccessModel]:
    return load_model(aws_path), load_cloud_model("azure", azure_path), load_cloud_model("gcp", gcp_path)


def multicloud_summary(
    aws_path: str | Path | None = None,
    azure_path: str | Path | None = None,
    gcp_path: str | Path | None = None,
) -> dict[str, Any]:
    """Lint Azure + GCP and build the cross-cloud matrix — the payload behind ``golden iam multicloud``."""
    aws, azure, gcp = load_all(aws_path, azure_path, gcp_path)
    azure_lint = lint_cloud_summary(azure)
    gcp_lint = lint_cloud_summary(gcp)
    matrix = persona_matrix(aws, azure, gcp)
    matrix_errors = any(f["severity"] == "error" for f in matrix["findings"])
    return {
        "valid": azure_lint["valid"] and gcp_lint["valid"] and not matrix_errors,
        "azure": azure_lint,
        "gcp": gcp_lint,
        "matrix": matrix,
    }
