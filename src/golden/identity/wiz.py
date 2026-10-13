"""Wiz.io findings → control gap assessment.

Loads a Wiz export — the Issues / Cloud Configuration Findings CSV from the console, or the JSON from
the GraphQL ``issues`` query (``data.issues.nodes``) — normalizes it, maps every finding onto the
control-placement catalog (:mod:`golden.identity.controls`) and produces a gap register: per control,
its status (``effective`` / ``partial`` / ``gap``), the open findings behind it, the layer it is placed
at and the remediation. Findings that match no identity control are reported as ``out_of_scope``.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from golden.identity.controls import CONTROLS, match_controls

SEVERITY_WEIGHT = {"critical": 10, "high": 5, "medium": 2, "low": 1, "informational": 0, "info": 0}
OPEN_STATUSES = {"open", "in_progress", "in progress", "fail", "failed", "active", ""}

# Column / field aliases seen across Wiz export formats (case-insensitive).
ALIASES = {
    "id": ("id", "issue id", "finding id", "issue_id"),
    "title": ("title", "rule", "rule name", "control", "control name", "issue", "name", "sourcerule"),
    "severity": ("severity", "risk", "severity level"),
    "status": ("status", "result", "issue status"),
    "resource_type": ("resource type", "entity type", "native type", "resource_type", "type"),
    "resource": ("resource name", "resource", "entity name", "resource_name", "resource external id"),
    "account": (
        "subscription id",
        "subscription",
        "account id",
        "cloud account",
        "subscription external id",
        "account",
    ),
    "cloud": ("cloud platform", "cloud", "cloud provider", "cloudplatform"),
    "description": ("description", "details"),
}


@dataclass
class CloudFinding:
    id: str
    title: str
    severity: str
    status: str
    resource_type: str = ""
    resource: str = ""
    account: str = ""
    cloud: str = "AWS"
    description: str = ""

    @property
    def is_open(self) -> bool:
        return self.status.lower() in OPEN_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pick(record: dict[str, Any], key: str) -> str:
    lowered = {str(k).strip().lower(): v for k, v in record.items()}
    for alias in ALIASES[key]:
        value = lowered.get(alias)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def normalize(record: dict[str, Any], index: int = 0) -> CloudFinding:
    # GraphQL issue node: flatten sourceRule / entitySnapshot.
    if "sourceRule" in record or "entitySnapshot" in record:
        rule = record.get("sourceRule") or {}
        entity = record.get("entitySnapshot") or {}
        record = {
            "id": record.get("id", ""),
            "title": rule.get("name", ""),
            "severity": record.get("severity", ""),
            "status": record.get("status", ""),
            "resource type": entity.get("nativeType") or entity.get("type", ""),
            "resource name": entity.get("name", ""),
            "subscription id": entity.get("subscriptionExternalId", ""),
            "cloud platform": entity.get("cloudPlatform", "AWS"),
            "description": record.get("description", ""),
        }
    title = _pick(record, "title")
    if not title:
        raise ValueError(f"finding #{index} has no title/rule name")
    return CloudFinding(
        id=_pick(record, "id") or f"finding-{index:05d}",
        title=title,
        severity=(_pick(record, "severity") or "medium").lower(),
        status=(_pick(record, "status") or "open").lower(),
        resource_type=_pick(record, "resource_type"),
        resource=_pick(record, "resource"),
        account=_pick(record, "account"),
        cloud=_pick(record, "cloud") or "AWS",
        description=_pick(record, "description"),
    )


def load_findings(path: str | Path) -> list[CloudFinding]:
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        # GraphQL response {"data": {"issues": {"nodes": [...]}}}, or a bare list of findings.
        if isinstance(data, dict):
            data = data.get("data", data)
            data = data.get("issues", data)
            data = data.get("nodes", []) if isinstance(data, dict) else data
        records = data if isinstance(data, list) else []
    else:
        records = list(csv.DictReader(text.splitlines()))
    return [normalize(r, i) for i, r in enumerate(records)]


def assess_gaps(findings: list[CloudFinding]) -> dict[str, Any]:
    open_findings = [f for f in findings if f.is_open]
    per_control: dict[str, list[CloudFinding]] = {c.id: [] for c in CONTROLS}
    out_of_scope: list[CloudFinding] = []
    for f in open_findings:
        matched = match_controls(f"{f.title} {f.resource_type}")
        if not matched:
            out_of_scope.append(f)
        for c in matched:
            per_control[c.id].append(f)

    register: list[dict[str, Any]] = []
    for c in CONTROLS:
        hits = per_control[c.id]
        severities = Counter(f.severity for f in hits)
        if severities["critical"] or severities["high"]:
            status = "gap"
        elif hits:
            status = "partial"
        else:
            status = "effective"
        register.append(
            {
                "control": c.id,
                "title": c.title,
                "status": status,
                "layers": list(c.layers),
                "open_findings": len(hits),
                "by_severity": dict(severities),
                "risk_points": sum(SEVERITY_WEIGHT.get(f.severity, 1) for f in hits),
                "affected_accounts": sorted({f.account for f in hits if f.account}),
                "examples": [f"{f.title} — {f.resource}".rstrip(" —") for f in hits[:3]],
                "remediation": c.remediation,
            }
        )
    register.sort(key=lambda r: (-r["risk_points"], r["control"]))
    statuses = Counter(r["status"] for r in register)
    in_scope_points = sum(SEVERITY_WEIGHT.get(f.severity, 1) for f in open_findings if f not in out_of_scope)
    return {
        "summary": {
            "findings": len(findings),
            "open": len(open_findings),
            "controls": len(register),
            "effective": statuses.get("effective", 0),
            "partial": statuses.get("partial", 0),
            "gaps": statuses.get("gap", 0),
            # 100 minus severity points of open in-scope findings (critical 10, high 5, medium 2, low 1).
            "identity_posture_score": max(0, 100 - in_scope_points),
            "out_of_scope": len(out_of_scope),
        },
        "register": register,
        "out_of_scope": [f.to_dict() for f in out_of_scope[:50]],
    }


def sample_findings() -> list[CloudFinding]:
    """A representative Wiz export for a mid-modernization AWS estate (demos and tests)."""
    rows = [
        (
            "Root account has active access keys",
            "critical",
            "AWS Account",
            "workloads-legacy",
            "888888888888",
        ),
        ("IAM user has access key older than 90 days", "high", "IAM User", "jenkins", "555555555555"),
        ("IAM user has access key older than 90 days", "high", "IAM User", "jenkins", "666666666666"),
        (
            "IAM user with console password without MFA",
            "high",
            "IAM User",
            "breakglass-legacy",
            "555555555555",
        ),
        (
            "Role with AdministratorAccess policy attached",
            "high",
            "IAM Role",
            "PingFed-Admins",
            "555555555555",
        ),
        (
            "Lambda function with high privileged role (*:*)",
            "critical",
            "Lambda",
            "legacy-lambda",
            "666666666666",
        ),
        (
            "Role is assumable by any AWS principal",
            "critical",
            "IAM Role",
            "debug-open-trust",
            "666666666666",
        ),
        ("Cross-account role without External ID", "high", "IAM Role", "vendor-backup", "555555555555"),
        (
            "IAM role not used in the last 90 days",
            "medium",
            "IAM Role",
            "workloads-prod-poc-00",
            "555555555555",
        ),
        (
            "IAM role not used in the last 90 days",
            "medium",
            "IAM Role",
            "workloads-nonprod-poc-01",
            "666666666666",
        ),
        (
            "Role without permissions boundary can create IAM roles (privilege escalation)",
            "high",
            "IAM Role",
            "old-jenkins",
            "555555555555",
        ),
        (
            "SAML identity provider configured outside IAM Identity Center",
            "medium",
            "SAML Provider",
            "PingFederate",
            "555555555555",
        ),
        (
            "S3 bucket policy allows access from external principals",
            "high",
            "S3 Bucket",
            "partner-drop",
            "555555555555",
        ),
        (
            "S3 bucket does not enforce SSL/TLS (secure transport)",
            "medium",
            "S3 Bucket",
            "app-logs",
            "666666666666",
        ),
        ("GuardDuty detector is not enabled", "medium", "Region", "ap-southeast-1", "666666666666"),
        (
            "EC2 instance has a public IP and an unpatched critical CVE",
            "critical",
            "Virtual Machine",
            "bastion-01",
            "666666666666",
        ),
        ("EBS volume is not encrypted", "low", "Volume", "vol-0abc", "555555555555"),
        (
            "Unused permissions on role (Access Analyzer)",
            "low",
            "IAM Role",
            "workloads-prod-api-ec2",
            "555555555555",
        ),
    ]
    return [
        CloudFinding(
            id=f"wiz-{i:04d}", title=t, severity=s, status="open", resource_type=rt, resource=r, account=a
        )
        for i, (t, s, rt, r, a) in enumerate(rows)
    ]
