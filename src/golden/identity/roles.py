"""IAM role inventory analysis — cleanup, consolidation and migration to IAM Identity Center.

Input is the standard ``aws iam get-account-authorization-details`` output (one account, or a list of
``{"account_id": ..., "details": ...}`` for many). Policy documents may be decoded objects (CLI) or
URL-encoded JSON strings (raw API); both are handled.

Every customer role gets findings and one **disposition**:

* ``remove``                    unused for ``unused_days`` (or never used) — governed ``delete_iam_role``
* ``migrate_to_permission_set`` direct SAML federation (e.g. PingFederate → IAM role) — move the
                                users to the closest persona in the access model
* ``consolidate``               same permissions and trust shape as another role — keep one
* ``remediate``                 high/critical findings (admin, open trust, no boundary on a used role…)
* ``keep``                      nothing to do

Service-linked roles and Identity Center-managed ``AWSReservedSSO_*`` roles are counted but not judged.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any
from urllib.parse import unquote

from golden.identity.model import PRIVILEGED_POLICIES, AccessModel

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
MANAGED_PATHS = ("/aws-service-role/", "/aws-reserved/sso.amazonaws.com/", "/service-role/aws-")


@dataclass
class RoleFinding:
    code: str
    severity: str
    message: str
    remediation: str


@dataclass
class RoleAnalysis:
    account_id: str
    role: str
    arn: str
    disposition: str
    managed_by_aws: bool = False
    last_used: str | None = None
    days_unused: int | None = None
    has_boundary: bool = False
    trust: str = "unknown"  # service | saml | oidc | same-account | cross-account | open
    fingerprint: str = ""
    suggested_persona: str | None = None
    consolidate_into: str | None = None
    governed_action: str | None = None
    findings: list[RoleFinding] = field(default_factory=list)

    @property
    def max_severity(self) -> str:
        return max((f.severity for f in self.findings), key=SEVERITY_ORDER.__getitem__, default="info")

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["max_severity"] = self.max_severity
        return out


# ----------------------------------------------------------------------------- parsing helpers
def _doc(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        return json.loads(unquote(raw))
    return {}


def _list(x: Any) -> list[Any]:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _statements(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in _list(doc.get("Statement")) if isinstance(s, dict)]


def _is_admin_statement(s: dict[str, Any]) -> bool:
    return (
        s.get("Effect") == "Allow" and "*" in _list(s.get("Action")) and "*" in _list(s.get("Resource", "*"))
    )


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _account_of(arn: str) -> str:
    parts = arn.split(":")
    return parts[4] if len(parts) > 4 else ""


def _accounts(details: dict[str, Any] | list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(details, list):
        return [(str(d.get("account_id", "")), d.get("details", d)) for d in details]
    return [("", details)]


# ----------------------------------------------------------------------------- analysis
def _trust_kind(
    trust: dict[str, Any], account_id: str, org_accounts: set[str]
) -> tuple[str, list[RoleFinding]]:
    findings: list[RoleFinding] = []
    kinds: set[str] = set()
    for s in _statements(trust):
        if s.get("Effect") != "Allow":
            continue
        principal = s.get("Principal", {})
        condition = s.get("Condition") or {}
        if principal == "*" or "*" in _list(principal.get("AWS") if isinstance(principal, dict) else None):
            kinds.add("open")
            if not condition:
                findings.append(
                    RoleFinding(
                        "OPEN_TRUST",
                        "critical",
                        "trust policy allows any AWS principal with no condition",
                        "Restrict Principal to specific accounts/roles and add aws:PrincipalOrgID",
                    )
                )
            continue
        if not isinstance(principal, dict):
            continue
        if principal.get("Service"):
            kinds.add("service")
        for fed in _list(principal.get("Federated")):
            kinds.add("saml" if ":saml-provider/" in fed else "oidc")
        for p in _list(principal.get("AWS")):
            other = p if p.isdigit() else _account_of(p)
            if other and other != account_id:
                kinds.add("cross-account")
                guarded = any(
                    key in cond
                    for cond in condition.values()
                    if isinstance(cond, dict)
                    for key in ("sts:ExternalId", "aws:PrincipalOrgID", "aws:PrincipalOrgPaths")
                )
                if not guarded:
                    external = other not in org_accounts
                    findings.append(
                        RoleFinding(
                            "CROSS_ACCOUNT_UNGUARDED",
                            "high" if external else "medium",
                            f"trusted by {'external ' if external else ''}account {other} without "
                            "sts:ExternalId or aws:PrincipalOrgID",
                            "Add an sts:ExternalId (third parties) or aws:PrincipalOrgID (internal) condition",
                        )
                    )
            else:
                kinds.add("same-account")
    for kind in ("open", "cross-account", "saml", "oidc", "same-account", "service"):
        if kind in kinds:
            return kind, findings
    return "unknown", findings


def _fingerprint(role: dict[str, Any]) -> str:
    """Effective-access identity: same permissions, same boundary and same trusted principals."""
    managed = sorted(p.get("PolicyArn", "") for p in role.get("AttachedManagedPolicies", []))
    inline = sorted(
        json.dumps(_doc(p.get("PolicyDocument")), sort_keys=True) for p in role.get("RolePolicyList", [])
    )
    principals = sorted(
        json.dumps(s.get("Principal"), sort_keys=True)
        for s in _statements(_doc(role.get("AssumeRolePolicyDocument")))
        if s.get("Effect") == "Allow"
    )
    boundary = (role.get("PermissionsBoundary") or {}).get("PermissionsBoundaryArn", "")
    raw = json.dumps(
        {"managed": managed, "inline": inline, "principals": principals, "boundary": boundary}, sort_keys=True
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _customer_policy_docs(details: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for policy in details.get("Policies", []):
        for version in policy.get("PolicyVersionList", []):
            if version.get("IsDefaultVersion"):
                out[policy.get("Arn", "")] = _doc(version.get("Document"))
    return out


def suggest_persona(role: dict[str, Any], model: AccessModel | None) -> str | None:
    """Closest persona by managed-policy overlap (Jaccard); read-only when nothing overlaps."""
    if model is None:
        return None
    names = {p.get("PolicyName", "") for p in role.get("AttachedManagedPolicies", [])}
    best, best_score = None, 0.0
    for persona in model.personas:
        if persona.privileged:
            continue  # never auto-map anyone to break-glass
        union = names | persona.policy_names
        score = len(names & persona.policy_names) / len(union) if union else 0.0
        if score > best_score:
            best, best_score = persona.name, score
    if best is None:
        fallback = model.persona("read-only") or next((p for p in model.personas if not p.privileged), None)
        return fallback.name if fallback else None
    return best


def analyze_role(
    role: dict[str, Any],
    *,
    account_id: str = "",
    now: datetime | None = None,
    unused_days: int = 90,
    boundary_name: str = "golden-workload-boundary",
    org_accounts: set[str] | None = None,
    customer_policies: dict[str, dict[str, Any]] | None = None,
    model: AccessModel | None = None,
) -> RoleAnalysis:
    now = now or datetime.now(UTC)
    arn = role.get("Arn", "")
    account_id = account_id or _account_of(arn)
    path = role.get("Path", "/")
    name = role.get("RoleName", arn.rsplit("/", 1)[-1])
    trust_kind, findings = _trust_kind(
        _doc(role.get("AssumeRolePolicyDocument")), account_id, org_accounts or set()
    )
    result = RoleAnalysis(
        account_id=account_id,
        role=name,
        arn=arn,
        disposition="keep",
        trust=trust_kind,
        fingerprint=_fingerprint(role),
    )
    if path.startswith(MANAGED_PATHS) or name.startswith("AWSReservedSSO_"):
        result.managed_by_aws, result.disposition = True, "managed"
        return result

    boundary = (role.get("PermissionsBoundary") or {}).get("PermissionsBoundaryArn", "")
    result.has_boundary = bool(boundary)
    last_used = _parse_date((role.get("RoleLastUsed") or {}).get("LastUsedDate"))
    created = _parse_date(role.get("CreateDate"))
    result.last_used = last_used.isoformat() if last_used else None
    reference = last_used or created
    result.days_unused = (now - reference).days if reference else None

    # --- permissions --------------------------------------------------------------------------
    managed = {
        p.get("PolicyName", ""): p.get("PolicyArn", "") for p in role.get("AttachedManagedPolicies", [])
    }
    admin = sorted(set(managed) & PRIVILEGED_POLICIES)
    for policy_arn in managed.values():
        doc = (customer_policies or {}).get(policy_arn)
        if doc and any(_is_admin_statement(s) for s in _statements(doc)):
            admin.append(policy_arn.rsplit("/", 1)[-1])
    inline = role.get("RolePolicyList", [])
    for p in inline:
        if any(_is_admin_statement(s) for s in _statements(_doc(p.get("PolicyDocument")))):
            admin.append(f"inline:{p.get('PolicyName', '?')}")
    if admin:
        findings.append(
            RoleFinding(
                "ADMIN_ACCESS",
                "high",
                f"administrator-equivalent permissions ({', '.join(admin)})",
                "Scope to required actions (IAM Access Analyzer policy generation) or move to break-glass",
            )
        )
    if inline:
        findings.append(
            RoleFinding(
                "INLINE_POLICY",
                "low",
                f"{len(inline)} inline polic{'y' if len(inline) == 1 else 'ies'}",
                "Replace with versioned customer-managed policies in Terraform",
            )
        )
    if not boundary:
        findings.append(
            RoleFinding(
                "NO_BOUNDARY",
                "medium",
                "no permission boundary",
                f"Attach {boundary_name} before the enforce-permission-boundary SCP reaches this OU",
            )
        )
    elif not boundary.endswith(f"/{boundary_name}"):
        findings.append(
            RoleFinding(
                "NONSTANDARD_BOUNDARY",
                "low",
                f"boundary {boundary.rsplit('/', 1)[-1]} is not {boundary_name}",
                f"Replace with {boundary_name}",
            )
        )

    # --- usage --------------------------------------------------------------------------------
    if last_used is None and result.days_unused is not None and result.days_unused >= unused_days:
        findings.append(
            RoleFinding(
                "NEVER_USED",
                "medium",
                f"never used since creation {result.days_unused} days ago",
                "Delete after owner confirmation",
            )
        )
    elif last_used is not None and result.days_unused is not None and result.days_unused >= unused_days:
        findings.append(
            RoleFinding(
                "UNUSED",
                "medium",
                f"last used {result.days_unused} days ago",
                "Delete after owner confirmation",
            )
        )
    if trust_kind == "saml":
        findings.append(
            RoleFinding(
                "LEGACY_SAML_FEDERATION",
                "medium",
                "workforce federation directly to an IAM role (per-account SAML provider)",
                "Move the users to an IAM Identity Center permission set via their AD group",
            )
        )

    result.findings = findings
    codes = {f.code for f in findings}
    if codes & {"UNUSED", "NEVER_USED"} and "OPEN_TRUST" not in codes:
        result.disposition, result.governed_action = "remove", "delete_iam_role"
    elif "LEGACY_SAML_FEDERATION" in codes:
        result.disposition = "migrate_to_permission_set"
        result.suggested_persona = suggest_persona(role, model)
    elif SEVERITY_ORDER[result.max_severity] >= SEVERITY_ORDER["high"] or "NO_BOUNDARY" in codes:
        result.disposition = "remediate"
    if "OPEN_TRUST" in codes:
        result.governed_action = "quarantine_iam_role"
    return result


def analyze_authorization_details(
    details: dict[str, Any] | list[dict[str, Any]],
    *,
    now: datetime | None = None,
    unused_days: int = 90,
    boundary_name: str = "golden-workload-boundary",
    org_accounts: set[str] | None = None,
    model: AccessModel | None = None,
) -> dict[str, Any]:
    if model is not None:
        boundary_name = model.permission_boundary or boundary_name
    results: list[RoleAnalysis] = []
    users: list[dict[str, Any]] = []
    for account_id, doc in _accounts(details):
        customer = _customer_policy_docs(doc)
        for role in doc.get("RoleDetailList", []):
            results.append(
                analyze_role(
                    role,
                    account_id=account_id,
                    now=now,
                    unused_days=unused_days,
                    boundary_name=boundary_name,
                    org_accounts=org_accounts,
                    customer_policies=customer,
                    model=model,
                )
            )
        for user in doc.get("UserDetailList", []):
            users.append(
                {
                    "account_id": account_id or _account_of(user.get("Arn", "")),
                    "user": user.get("UserName"),
                    "arn": user.get("Arn"),
                    "groups": user.get("GroupList", []),
                    "finding": "IAM_USER",
                    "remediation": "Replace with Identity Center (people) or IAM Roles Anywhere / workload roles (machines)",
                }
            )

    # Consolidation: roles in the same account with identical permissions + trust shape.
    groups: dict[tuple[str, str], list[RoleAnalysis]] = defaultdict(list)
    for r in results:
        # IRSA/OIDC roles are bound to one service account each; open trust is remediated first.
        if r.disposition in {"keep", "remediate"} and r.trust not in {"oidc", "open"}:
            groups[(r.account_id, r.fingerprint)].append(r)
    consolidation = []
    for (account_id, fp), members in groups.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda r: (r.days_unused if r.days_unused is not None else 10**6, r.role))
        keeper = members[0]
        for dup in members[1:]:
            dup.disposition, dup.consolidate_into = "consolidate", keeper.role
        consolidation.append(
            {
                "account_id": account_id,
                "fingerprint": fp,
                "keep": keeper.role,
                "retire": [m.role for m in members[1:]],
            }
        )

    customer_roles = [r for r in results if not r.managed_by_aws]
    by_disposition = Counter(r.disposition for r in results)
    reducible = sum(by_disposition[d] for d in ("remove", "consolidate", "migrate_to_permission_set"))
    by_code = Counter(f.code for r in customer_roles for f in r.findings)
    return {
        "summary": {
            "roles": len(results),
            "customer_roles": len(customer_roles),
            "aws_managed_roles": len(results) - len(customer_roles),
            "iam_users": len(users),
            "by_disposition": dict(sorted(by_disposition.items())),
            "role_reduction_pct": round(100 * reducible / len(customer_roles), 1) if customer_roles else 0.0,
            "boundary_coverage_pct": round(
                100 * sum(r.has_boundary for r in customer_roles) / len(customer_roles), 1
            )
            if customer_roles
            else 100.0,
            "top_findings": by_code.most_common(8),
        },
        "consolidation": consolidation,
        "iam_users": users,
        "roles": [
            r.to_dict() for r in sorted(results, key=lambda r: (-SEVERITY_ORDER[r.max_severity], r.arn))
        ],
    }


# ----------------------------------------------------------------------------- sample estate
def _trust(principal: dict[str, Any], action: str = "sts:AssumeRole", condition: dict | None = None) -> dict:
    stmt: dict[str, Any] = {"Effect": "Allow", "Principal": principal, "Action": action}
    if condition:
        stmt["Condition"] = condition
    return {"Version": "2012-10-17", "Statement": [stmt]}


def _sample_role(
    roles: list[dict[str, Any]],
    account_id: str,
    now: datetime,
    name: str,
    trust: dict,
    managed: list[str],
    *,
    days_since_use: int | None = 3,
    age: int = 900,
    boundary: bool = False,
    inline: list[dict] | None = None,
    path: str = "/",
) -> None:
    entry: dict[str, Any] = {
        "Path": path,
        "RoleName": name,
        "Arn": f"arn:aws:iam::{account_id}:role{path}{name}",
        "CreateDate": (now - timedelta(days=age)).isoformat(),
        "AssumeRolePolicyDocument": trust,
        "AttachedManagedPolicies": [
            {"PolicyName": m.rsplit("/", 1)[-1], "PolicyArn": f"arn:aws:iam::aws:policy/{m}"} for m in managed
        ],
        "RolePolicyList": inline or [],
        "RoleLastUsed": (
            {"LastUsedDate": (now - timedelta(days=days_since_use)).isoformat(), "Region": "us-east-1"}
            if days_since_use is not None
            else {}
        ),
    }
    if boundary:
        entry["PermissionsBoundary"] = {
            "PermissionsBoundaryType": "Policy",
            "PermissionsBoundaryArn": f"arn:aws:iam::{account_id}:policy/golden-workload-boundary",
        }
    roles.append(entry)


def sample_authorization_details(seed: int = 7, now: datetime | None = None) -> list[dict[str, Any]]:
    """A realistic two-account estate before IAM modernization (for demos and tests)."""
    rng = random.Random(seed)
    now = now or datetime(2026, 10, 1, tzinfo=UTC)
    accounts = {"555555555555": "workloads-prod", "666666666666": "workloads-nonprod"}
    out = []
    for account_id, label in accounts.items():
        roles: list[dict[str, Any]] = []

        role = partial(_sample_role, roles, account_id, now)

        saml = _trust(
            {"Federated": f"arn:aws:iam::{account_id}:saml-provider/PingFederate"},
            "sts:AssumeRoleWithSAML",
            {"StringEquals": {"SAML:aud": "https://signin.aws.amazon.com/saml"}},
        )
        ec2 = _trust({"Service": "ec2.amazonaws.com"})
        lam = _trust({"Service": "lambda.amazonaws.com"})
        # Legacy PingFederate → IAM role federation (pre-Identity Center)
        role("PingFed-Admins", saml, ["AdministratorAccess"])
        role("PingFed-Developers", saml, ["PowerUserAccess"])
        role("PingFed-ReadOnly", saml, ["job-function/ViewOnlyAccess"])
        role("PingFed-Auditors", saml, ["SecurityAudit", "job-function/ViewOnlyAccess"], days_since_use=40)
        role("PingFed-NetOps", saml, ["job-function/NetworkAdministrator"], days_since_use=150)
        # Workload roles
        role(f"{label}-api-ec2", ec2, ["AmazonSSMManagedInstanceCore"], boundary=True)
        role(f"{label}-batch-ec2", ec2, ["AmazonSSMManagedInstanceCore"])
        role(f"{label}-batch-ec2-copy", ec2, ["AmazonSSMManagedInstanceCore"], days_since_use=20)
        role(f"{label}-etl-lambda", lam, ["service-role/AWSLambdaBasicExecutionRole"], boundary=True)
        role(
            f"{label}-legacy-lambda",
            lam,
            ["service-role/AWSLambdaBasicExecutionRole"],
            inline=[
                {
                    "PolicyName": "everything",
                    "PolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}],
                    },
                }
            ],
        )
        for i in range(rng.randint(3, 5)):
            role(
                f"{label}-poc-{i:02d}",
                ec2,
                ["AmazonS3FullAccess"],
                days_since_use=None,
                age=rng.randint(120, 700),
            )
        role(f"{label}-old-jenkins", ec2, ["PowerUserAccess"], days_since_use=rng.randint(200, 400))
        # Cross-account / third party
        role(
            f"{label}-vendor-backup",
            _trust({"AWS": "arn:aws:iam::999988887777:root"}),
            ["AWSBackupFullAccess"],
        )
        role(
            "WizAccess-Role",
            _trust(
                {"AWS": "arn:aws:iam::197171649850:role/wiz-scanner"},
                condition={"StringEquals": {"sts:ExternalId": "wiz-tenant-0000000000"}},
            ),
            ["SecurityAudit", "job-function/ViewOnlyAccess"],
            boundary=True,
        )
        role(
            f"{label}-shared-deploy",
            _trust({"AWS": "arn:aws:iam::333333333333:role/ci-deployer"}),
            ["PowerUserAccess"],
        )
        if label == "workloads-nonprod":
            role("debug-open-trust", _trust({"AWS": "*"}), ["ReadOnlyAccess"], days_since_use=12)
        # AWS-managed roles that must be left alone
        role(
            "AWSServiceRoleForSupport",
            _trust({"Service": "support.amazonaws.com"}),
            ["AWSSupportServiceRolePolicy"],
            path="/aws-service-role/support.amazonaws.com/",
        )
        role(
            "AWSReservedSSO_ReadOnly_0123456789abcdef",
            _trust(
                {"Federated": f"arn:aws:iam::{account_id}:saml-provider/AWSSSO_0123_DO_NOT_DELETE"},
                "sts:AssumeRoleWithSAML",
            ),
            ["job-function/ViewOnlyAccess"],
            path="/aws-reserved/sso.amazonaws.com/",
        )
        users = [
            {"UserName": "jenkins", "Arn": f"arn:aws:iam::{account_id}:user/jenkins", "GroupList": []},
            {
                "UserName": "breakglass-legacy",
                "Arn": f"arn:aws:iam::{account_id}:user/breakglass-legacy",
                "GroupList": ["Admins"],
            },
        ]
        out.append(
            {
                "account_id": account_id,
                "details": {"RoleDetailList": roles, "UserDetailList": users, "Policies": []},
            }
        )
    return out
