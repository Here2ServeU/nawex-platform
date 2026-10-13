"""AWS identity governance: access model, role cleanup, Wiz gap assessment, guardrail templates."""

from __future__ import annotations

import copy
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import pytest
import yaml

from golden.cli import main
from golden.identity import (
    CONTROLS,
    analyze_authorization_details,
    analyze_role,
    assess_gaps,
    lint_model,
    load_findings,
    load_model,
    parse_model,
    sample_authorization_details,
    sample_findings,
)
from golden.identity.controls import LAYERS
from golden.identity.model import session_hours

ROOT = Path(__file__).resolve().parents[1]
MODEL_FILE = ROOT / "security/identity/access-model.yaml"
GUARDRAILS = ROOT / "deploy/terraform/modules/aws/org-guardrails/policies"
NOW = datetime(2026, 10, 1, tzinfo=UTC)


def raw_model() -> dict:
    return yaml.safe_load(MODEL_FILE.read_text())


def codes(model_dict: dict) -> set[str]:
    return {f.code for f in lint_model(parse_model(model_dict))}


# ----------------------------------------------------------------------------- access model
def test_shipped_access_model_is_clean():
    model = load_model(MODEL_FILE)
    assert lint_model(model) == []
    assert [p.name for p in model.personas if p.privileged] == ["break-glass"]
    # Developers read prod but only build in non-prod.
    grants = model.group_map()["AWS-Developers"]
    assert {(g["permission_set"], tuple(g["account_groups"])) for g in grants} == {
        ("ReadOnly", ("workloads-prod",)),
        ("Developer", ("workloads-nonprod", "sandbox")),
    }


@pytest.mark.parametrize(
    ("persona", "patch", "expected"),
    [
        ("developer", {"aws_managed_policies": ["AdministratorAccess"]}, "PRIVILEGED_POLICY"),
        ("developer", {"permissions_boundary": False}, "BROAD_POLICY_WITHOUT_BOUNDARY"),
        ("developer", {"session_duration": "PT12H"}, "SESSION_TOO_LONG"),
        ("break-glass", {"session_duration": "PT2H"}, "PRIVILEGED_SESSION_TOO_LONG"),
        ("read-only", {"session_duration": "8 hours"}, "INVALID_SESSION"),
        ("read-only", {"permission_set": "x" * 40}, "INVALID_NAME"),
        (
            "read-only",
            {"assignments": [{"group": "aws_readonly", "account_groups": ["sandbox"]}]},
            "GROUP_NAMING",
        ),
        (
            "read-only",
            {"assignments": [{"group": "AWS-ReadOnly", "account_groups": ["mars"]}]},
            "UNKNOWN_ACCOUNT_GROUP",
        ),
        (
            "read-only",
            {"assignments": [{"group": "AWS-ReadOnly", "account_groups": ["management"]}]},
            "MANAGEMENT_ACCOUNT_ACCESS",
        ),
        ("read-only", {"assignments": []}, "UNASSIGNED"),
        (
            "sre-oncall",
            {"inline_policy": [{"Sid": "x", "Effect": "Allow", "Action": "*", "Resource": "*"}]},
            "WILDCARD_INLINE",
        ),
    ],
)
def test_lint_catches_design_mistakes(persona, patch, expected):
    data = raw_model()
    target = next(p for p in data["personas"] if p["name"] == persona)
    target.update(patch)
    assert expected in codes(data)


def test_delegated_iam_requires_boundary():
    data = raw_model()
    data["personas"].append(
        {
            "name": "x",
            "permission_set": "X",
            "delegated_iam": True,
            "assignments": [{"group": "AWS-X", "account_groups": ["sandbox"]}],
        }
    )
    assert "DELEGATED_IAM_WITHOUT_BOUNDARY" in codes(data)


def test_session_parsing():
    assert session_hours("PT8H") == 8 and session_hours("PT1H30M") == 1.5 and session_hours("PT45M") == 0.75
    with pytest.raises(ValueError):
        session_hours("PT")


def test_model_requires_personas():
    with pytest.raises(ValueError):
        parse_model({"personas": []})


# ----------------------------------------------------------------------------- role analysis
@pytest.fixture(scope="module")
def estate() -> dict:
    return analyze_authorization_details(
        sample_authorization_details(now=NOW),
        now=NOW,
        model=load_model(MODEL_FILE),
        org_accounts={"333333333333", "555555555555", "666666666666"},
    )


def _role(result: dict, account: str, name: str) -> dict:
    return next(r for r in result["roles"] if r["account_id"] == account and r["role"] == name)


def test_role_dispositions(estate):
    s = estate["summary"]
    assert s["aws_managed_roles"] == 4 and s["iam_users"] == 4
    assert {"remove", "consolidate", "migrate_to_permission_set", "remediate", "keep"} <= set(
        s["by_disposition"]
    )
    assert 0 < s["boundary_coverage_pct"] < 50 and s["role_reduction_pct"] > 40

    assert _role(estate, "555555555555", "PingFed-Developers")["suggested_persona"] == "developer"
    assert _role(estate, "555555555555", "PingFed-Auditors")["suggested_persona"] == "security-auditor"
    # Admin federation is never auto-mapped to break-glass.
    assert _role(estate, "555555555555", "PingFed-Admins")["suggested_persona"] != "break-glass"

    unused = _role(estate, "555555555555", "workloads-prod-old-jenkins")
    assert unused["disposition"] == "remove" and unused["governed_action"] == "delete_iam_role"

    open_trust = _role(estate, "666666666666", "debug-open-trust")
    assert open_trust["max_severity"] == "critical" and open_trust["governed_action"] == "quarantine_iam_role"

    assert _role(estate, "555555555555", "WizAccess-Role")["disposition"] == "keep"
    assert _role(estate, "555555555555", "AWSServiceRoleForSupport")["disposition"] == "managed"


def test_consolidation_keeps_most_recently_used(estate):
    groups = {c["keep"]: c["retire"] for c in estate["consolidation"]}
    assert groups["workloads-prod-batch-ec2"] == ["workloads-prod-batch-ec2-copy"]
    assert (
        _role(estate, "555555555555", "workloads-prod-batch-ec2-copy")["consolidate_into"]
        == "workloads-prod-batch-ec2"
    )


def test_cross_account_trust_severity(estate):
    vendor = _role(estate, "555555555555", "workloads-prod-vendor-backup")
    internal = _role(estate, "555555555555", "workloads-prod-shared-deploy")
    sev = {f["code"]: f["severity"] for f in vendor["findings"]}
    assert sev["CROSS_ACCOUNT_UNGUARDED"] == "high"  # third party, outside the org
    assert {f["code"]: f["severity"] for f in internal["findings"]}["CROSS_ACCOUNT_UNGUARDED"] == "medium"


def test_url_encoded_documents_and_customer_admin_policies():
    """Raw IAM API output URL-encodes policy documents; customer policies can hide admin."""
    trust = {
        "Statement": [
            {"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}
        ]
    }
    admin_doc = {"Statement": [{"Effect": "Allow", "Action": ["*"], "Resource": "*"}]}
    role = {
        "RoleName": "app",
        "Arn": "arn:aws:iam::123456789012:role/app",
        "Path": "/",
        "AssumeRolePolicyDocument": quote(json.dumps(trust)),
        "AttachedManagedPolicies": [
            {"PolicyName": "AppAll", "PolicyArn": "arn:aws:iam::123456789012:policy/AppAll"}
        ],
        "RoleLastUsed": {"LastUsedDate": "2026-09-30T00:00:00Z"},
        "PermissionsBoundary": {
            "PermissionsBoundaryArn": "arn:aws:iam::123456789012:policy/golden-workload-boundary"
        },
    }
    result = analyze_role(
        role, now=NOW, customer_policies={"arn:aws:iam::123456789012:policy/AppAll": admin_doc}
    )
    assert result.trust == "service"
    assert [f.code for f in result.findings] == ["ADMIN_ACCESS"]
    assert result.disposition == "remediate"


def test_single_account_details_without_wrapper():
    details = sample_authorization_details(now=NOW)[0]["details"]
    result = analyze_authorization_details(details, now=NOW)
    assert result["summary"]["roles"] == len(details["RoleDetailList"])


# ----------------------------------------------------------------------------- Wiz gap assessment
def test_gap_assessment_on_sample():
    result = assess_gaps(sample_findings())
    status = {r["control"]: r["status"] for r in result["register"]}
    assert status["IAM-01"] == "gap" and status["IAM-02"] == "gap" and status["IAM-07"] == "gap"
    assert status["GOV-02"] == "effective"
    assert result["summary"]["out_of_scope"] == 2  # CVE + EBS encryption are not identity controls
    assert 0 <= result["summary"]["identity_posture_score"] < 100


def test_wiz_csv_export_with_aliases_and_closed_findings(tmp_path):
    csv_file = tmp_path / "wiz-issues.csv"
    csv_file.write_text(
        "Issue ID,Rule Name,Severity,Status,Resource Type,Resource Name,Subscription ID\n"
        "1,IAM user has access key older than 90 days,HIGH,OPEN,IAM User,ci,555555555555\n"
        "2,Root account has active access keys,CRITICAL,RESOLVED,AWS Account,root,555555555555\n"
        "3,S3 bucket does not enforce SSL/TLS,MEDIUM,IN_PROGRESS,S3 Bucket,logs,666666666666\n",
        encoding="utf-8",
    )
    findings = load_findings(csv_file)
    assert [f.severity for f in findings] == ["high", "critical", "medium"]
    result = assess_gaps(findings)
    status = {r["control"]: r["status"] for r in result["register"]}
    assert result["summary"]["open"] == 2
    assert status["IAM-02"] == "gap" and status["IAM-01"] == "effective" and status["DP-02"] == "partial"


def test_wiz_graphql_json(tmp_path):
    payload = {
        "data": {
            "issues": {
                "nodes": [
                    {
                        "id": "abc",
                        "severity": "HIGH",
                        "status": "OPEN",
                        "sourceRule": {"name": "Cross-account role without External ID"},
                        "entitySnapshot": {
                            "type": "IAM_ROLE",
                            "name": "vendor",
                            "subscriptionExternalId": "555555555555",
                        },
                    }
                ]
            }
        }
    }
    path = tmp_path / "issues.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    (finding,) = load_findings(path)
    assert finding.account == "555555555555" and finding.resource == "vendor"
    register = {r["control"]: r for r in assess_gaps([finding])["register"]}
    assert register["IAM-07"]["status"] == "gap"


# ----------------------------------------------------------------------------- catalog & IaC consistency
def test_controls_reference_real_artifacts():
    assert len({c.id for c in CONTROLS}) == len(CONTROLS)
    for c in CONTROLS:
        assert set(c.layers) <= set(LAYERS), c.id
        for path in c.implemented_by:
            assert (ROOT / path).exists(), f"{c.id}: {path} missing"


def _render(template: Path) -> dict:
    values = {
        "partition": "aws",
        "org_id": "o-abc123def4",
        "boundary_policy_name": "golden-workload-boundary",
        "exempt_principals": json.dumps(["arn:*:iam::*:role/golden-terraform-deployer"]),
        "allowed_regions": json.dumps(["us-east-1", "us-west-2"]),
    }
    text = re.sub(r"\$\{(\w+)\}", lambda m: values[m.group(1)], template.read_text())
    return json.loads(text)


@pytest.mark.parametrize("template", sorted(GUARDRAILS.glob("*/*.json.tftpl")), ids=lambda p: p.name)
def test_guardrail_templates_render_within_size_limit(template):
    policy = _render(template)
    assert policy["Version"] == "2012-10-17" and policy["Statement"]
    assert len(json.dumps(policy, separators=(",", ":"))) <= 5120
    for statement in policy["Statement"]:
        assert statement["Effect"] == "Deny"  # guardrails only ever deny
        if template.parent.name == "rcp":
            assert statement["Principal"] == "*"  # RCPs require Principal "*"


def test_boundary_name_is_consistent_across_layers():
    name = raw_model()["permission_boundary"]
    for path in (
        "deploy/terraform/modules/aws/permission-boundary/variables.tf",
        "deploy/terraform/modules/aws/org-guardrails/variables.tf",
        "security/policies/opa/aws-iam.rego",
    ):
        assert f'"{name}"' in (ROOT / path).read_text(), path


# ----------------------------------------------------------------------------- CLI
def test_iam_cli(capsys):
    assert main(["iam", "model", "--model", str(MODEL_FILE)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    main(["iam", "roles", "--model", str(MODEL_FILE)])
    out = json.loads(capsys.readouterr().out)
    assert out["summary"]["customer_roles"] > 0 and out["actions"]
    main(["iam", "gaps"])
    assert json.loads(capsys.readouterr().out)["summary"]["gaps"] > 0
    main(["iam", "controls"])
    assert len(json.loads(capsys.readouterr().out)) == len(CONTROLS)


def test_iam_cli_model_lint_fails_on_bad_model(tmp_path, capsys):
    data = copy.deepcopy(raw_model())
    data["personas"][0]["aws_managed_policies"] = ["AdministratorAccess"]
    bad = tmp_path / "model.yaml"
    bad.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert main(["iam", "model", "--model", str(bad)]) == 1
    assert json.loads(capsys.readouterr().out)["valid"] is False
