"""Cloud security control-placement catalog for AWS identity governance.

Every control is placed at the layer that can enforce it most reliably — the earliest one wins:

    pipeline (OPA on the Terraform plan)  →  org preventive (SCP)  →  resource preventive (RCP)
    →  identity preventive (permission boundary)  →  access design (Identity Center persona)
    →  detective (Wiz / Security Hub)  →  IdP (PingFederate / AD)

``implemented_by`` points at the repository artifacts that implement the control (tests assert they
exist). ``wiz_patterns`` map Wiz issue / rule titles onto the control for the gap assessment.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

LAYERS = (
    "pipeline",
    "preventive-org",
    "preventive-resource",
    "preventive-identity",
    "access-design",
    "detective",
    "idp",
)


@dataclass(frozen=True)
class Control:
    id: str
    title: str
    layers: tuple[str, ...]
    implemented_by: tuple[str, ...]
    remediation: str
    wiz_patterns: tuple[str, ...] = field(default_factory=tuple)

    def matches(self, text: str) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in self.wiz_patterns)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SCP = "deploy/terraform/modules/aws/org-guardrails/policies/scp"
RCP = "deploy/terraform/modules/aws/org-guardrails/policies/rcp"
OPA = "security/policies/opa/aws-iam.rego"
MODEL = "security/identity/access-model.yaml"

CONTROLS: tuple[Control, ...] = (
    Control(
        "IAM-01",
        "Root user locked down",
        ("preventive-org", "detective"),
        (f"{SCP}/deny-root-and-iam-users.json.tftpl",),
        "Attach deny-root-and-iam-users to every OU; enable centralized root access and remove root credentials.",
        (r"\broot\b.*(access key|mfa|used|login|activity|credential)", r"root (user|account)"),
    ),
    Control(
        "IAM-02",
        "No long-lived IAM user credentials",
        ("pipeline", "preventive-org", "preventive-identity", "detective"),
        (
            f"{SCP}/deny-root-and-iam-users.json.tftpl",
            OPA,
            "deploy/terraform/modules/aws/permission-boundary/main.tf",
        ),
        "Move people to Identity Center and machines to workload roles / IAM Roles Anywhere; delete access keys.",
        (
            r"access key",
            r"iam user",
            r"(console|password).*user",
            r"user.*(password|console)",
            r"long.?lived",
        ),
    ),
    Control(
        "IAM-03",
        "Permission boundary on every role",
        ("pipeline", "preventive-org", "preventive-identity"),
        (
            f"{SCP}/enforce-permission-boundary.json.tftpl",
            "deploy/terraform/modules/aws/permission-boundary/main.tf",
            OPA,
        ),
        "Backfill golden-workload-boundary on existing roles (`golden iam roles` NO_BOUNDARY), then attach the SCP.",
        (r"permissions? boundar", r"privilege escalation", r"escalat"),
    ),
    Control(
        "IAM-04",
        "Least privilege — no standing admin",
        ("pipeline", "access-design", "detective"),
        (OPA, MODEL, "src/golden/identity/roles.py"),
        "Right-size with IAM Access Analyzer unused-access findings; admin only through the BreakGlassAdmin permission set.",
        (
            r"admin(istrator)?\s*(access|privileges|permissions|role)",
            r"full access",
            r"\*:\*",
            r"excessive|over.?privileged|high.?privileged",
            r"unused permissions?",
        ),
    ),
    Control(
        "IAM-05",
        "Workforce access only through IAM Identity Center",
        ("access-design", "detective"),
        (
            MODEL,
            "deploy/terraform/modules/aws/identity-center/main.tf",
            f"{SCP}/protect-security-services.json.tftpl",
        ),
        "Migrate per-account PingFederate SAML roles to permission sets (`golden iam roles` migrate_to_permission_set).",
        (r"saml", r"federat", r"identity provider", r"\bsso\b"),
    ),
    Control(
        "IAM-06",
        "Phishing-resistant MFA for every human",
        ("idp",),
        (MODEL,),
        "Enforce MFA in the PingFederate / PingID authentication policy for the AWS Identity Center SP connection.",
        (r"\bmfa\b", r"multi.?factor"),
    ),
    Control(
        "IAM-07",
        "Hardened cross-account trust",
        ("pipeline", "preventive-resource", "detective"),
        (OPA, f"{RCP}/data-perimeter.json.tftpl", "deploy/terraform/modules/aws/wiz-connector/main.tf"),
        "Require sts:ExternalId for third parties and aws:PrincipalOrgID for internal trust; the RCP blocks the rest.",
        (
            r"cross.?account",
            r"external.?id",
            r"trust polic",
            r"third.?party",
            r"assum(e|able) by (any|external)",
        ),
    ),
    Control(
        "IAM-08",
        "Unused roles and credentials removed",
        ("detective", "access-design"),
        ("src/golden/identity/roles.py",),
        "Delete roles unused for 90 days through the governed delete_iam_role action after owner sign-off.",
        (r"unused", r"inactive", r"stale", r"not (been )?used", r"dormant"),
    ),
    Control(
        "IAM-09",
        "Bounded session duration",
        ("pipeline", "access-design"),
        (OPA, MODEL),
        "Cap permission-set sessions at 8h (1h privileged) and role max_session_duration at 1h for humans.",
        (r"session duration",),
    ),
    Control(
        "DP-01",
        "Data perimeter — only org identities reach org resources",
        ("preventive-resource", "detective"),
        (f"{RCP}/data-perimeter.json.tftpl",),
        "Attach the data-perimeter RCP; tag sanctioned exceptions dp:exclude:identity=true.",
        (
            r"public(ly)?\s*(accessible|exposed|read|write)",
            r"external (principal|access|identit)",
            r"anonymous",
            r"cross.?organi[sz]ation",
            r"bucket polic",
            r"resource.?based polic",
        ),
    ),
    Control(
        "DP-02",
        "Encryption in transit enforced",
        ("preventive-resource",),
        (f"{RCP}/data-perimeter.json.tftpl",),
        "The data-perimeter RCP denies non-TLS requests to S3, SQS, KMS, Secrets Manager and STS.",
        (r"\b(ssl|tls|https)\b", r"secure transport", r"in transit"),
    ),
    Control(
        "GOV-01",
        "Security services cannot be disabled",
        ("preventive-org", "preventive-identity"),
        (
            f"{SCP}/protect-security-services.json.tftpl",
            "deploy/terraform/modules/aws/permission-boundary/main.tf",
        ),
        "Attach protect-security-services org-wide; re-enable any disabled service from the delegated admin.",
        (
            r"cloudtrail",
            r"guardduty",
            r"security ?hub",
            r"config (recorder|rule|not enabled|disabled)",
            r"logging (is )?(disabled|not enabled)",
        ),
    ),
    Control(
        "GOV-02",
        "Region allow-list",
        ("preventive-org",),
        (f"{SCP}/region-allowlist.json.tftpl",),
        "Attach region-allowlist; extend allowed_regions through a reviewed change.",
        (r"unapproved region", r"region (restriction|not allowed)", r"disallowed region"),
    ),
    Control(
        "GOV-03",
        "Policy-as-code gate on every IAM change",
        ("pipeline",),
        (OPA, "scripts/iam-policy-gate.sh"),
        "Run scripts/iam-policy-gate.sh on every Terraform plan (make iam-plan; CI infra workflow).",
        (r"infrastructure.?as.?code", r"\biac\b"),
    ),
    Control(
        "DET-01",
        "Continuous posture assessment",
        ("detective",),
        ("deploy/terraform/modules/aws/wiz-connector/main.tf", "src/golden/identity/wiz.py"),
        "Connect every account to Wiz with the read-only connector role; review `golden iam gaps` weekly.",
        (),
    ),
)


def control(control_id: str) -> Control:
    for c in CONTROLS:
        if c.id == control_id:
            return c
    raise KeyError(control_id)


def match_controls(text: str) -> list[Control]:
    return [c for c in CONTROLS if c.matches(text)]


def catalog() -> list[dict[str, Any]]:
    return [c.to_dict() for c in CONTROLS]
