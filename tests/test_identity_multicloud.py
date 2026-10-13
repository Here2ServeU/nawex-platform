"""Multi-cloud identity governance: Azure + GCP access models, lint rules, cross-cloud persona matrix."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from golden.identity.model import load_model
from golden.identity.multicloud import (
    lint_cloud_model,
    lint_cloud_summary,
    load_cloud_model,
    multicloud_summary,
    parse_cloud_model,
    persona_matrix,
)

ROOT = Path(__file__).resolve().parents[1]
AWS_FILE = ROOT / "security/identity/access-model.yaml"
AZURE_FILE = ROOT / "security/identity/azure-access-model.yaml"
GCP_FILE = ROOT / "security/identity/gcp-access-model.yaml"
AZURE_MODULE = ROOT / "deploy/terraform/modules/azure/governance"
GCP_MODULE = ROOT / "deploy/terraform/modules/gcp/org-governance"


def raw(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def codes(data: dict, cloud: str) -> set[str]:
    return {f.code for f in lint_cloud_model(parse_cloud_model(data, cloud))}


def persona(data: dict, name: str) -> dict:
    return next(p for p in data["personas"] if p["name"] == name)


# ----------------------------------------------------------------------------- shipped models
def test_shipped_azure_model_is_clean():
    model = load_cloud_model("azure", AZURE_FILE)
    assert lint_cloud_model(model) == []
    assert [p.name for p in model.personas if p.privileged] == ["break-glass"]
    owners = [p.name for p in model.personas if "Owner" in p.roles]
    assert owners == ["break-glass"]


def test_shipped_gcp_model_is_clean_and_expands_domain():
    model = load_cloud_model("gcp", GCP_FILE)
    assert lint_cloud_model(model) == []
    assert all("${domain}" not in g for g in model.group_map())
    assert "gcp-break-glass@example.com" in model.group_map()
    assert [p.name for p in model.personas if "roles/owner" in p.roles] == ["break-glass"]


def test_shipped_models_cover_the_same_personas_across_three_clouds():
    summary = multicloud_summary(AWS_FILE, AZURE_FILE, GCP_FILE)
    assert summary["valid"] is True
    matrix = summary["matrix"]
    assert matrix["clouds"] == ["aws", "azure", "gcp"]
    assert matrix["consistent"] is True
    row = next(r for r in matrix["personas"] if r["persona"] == "break-glass")
    assert row["aws"]["permission_set"] == "BreakGlassAdmin"
    assert row["azure"]["roles"] == ["Owner"]
    assert "roles/owner" in row["gcp"]["roles"]


def test_env_var_selects_model(monkeypatch, tmp_path):
    target = tmp_path / "az.yaml"
    target.write_text(AZURE_FILE.read_text())
    monkeypatch.setenv("GOLDEN_AZURE_ACCESS_MODEL", str(target))
    assert load_cloud_model("azure").cloud == "azure"
    monkeypatch.setenv("GOLDEN_GCP_ACCESS_MODEL", str(tmp_path / "missing.yaml"))
    with pytest.raises(FileNotFoundError, match="GOLDEN_GCP_ACCESS_MODEL"):
        load_cloud_model("gcp")


def test_parse_rejects_bad_input():
    with pytest.raises(ValueError, match="personas"):
        parse_cloud_model({"personas": []}, "azure")
    with pytest.raises(ValueError, match="unknown cloud"):
        parse_cloud_model(raw(AZURE_FILE), "oci")


# ----------------------------------------------------------------------------- lint rules
@pytest.mark.parametrize(
    ("cloud", "path", "role"), [("azure", AZURE_FILE, "Owner"), ("gcp", GCP_FILE, "roles/owner")]
)
def test_owner_outside_break_glass_is_an_error(cloud, path, role):
    data = copy.deepcopy(raw(path))
    persona(data, "developer")["roles"].append(role)
    assert "PRIVILEGED_ROLE" in codes(data, cloud)


def test_azure_user_access_administrator_is_privileged():
    data = copy.deepcopy(raw(AZURE_FILE))
    persona(data, "platform-engineer")["roles"] = ["User Access Administrator"]
    assert "PRIVILEGED_ROLE" in codes(data, "azure")


@pytest.mark.parametrize(
    ("cloud", "path", "standing"), [("azure", AZURE_FILE, "active"), ("gcp", GCP_FILE, "binding")]
)
def test_break_glass_must_be_just_in_time_and_approved(cloud, path, standing):
    data = copy.deepcopy(raw(path))
    bg = persona(data, "break-glass")
    bg["assignment"] = standing
    bg["require_approval"] = False
    found = codes(data, cloud)
    assert {"STANDING_PRIVILEGE", "PRIVILEGED_WITHOUT_APPROVAL"} <= found


def test_pim_activation_limits():
    data = copy.deepcopy(raw(AZURE_FILE))
    persona(data, "platform-engineer")["activation_duration"] = "PT12H"
    persona(data, "break-glass")["activation_duration"] = "PT2H"
    found = codes(data, "azure")
    assert {"ACTIVATION_TOO_LONG", "PRIVILEGED_ACTIVATION_TOO_LONG"} <= found


def test_gcp_entitlement_needs_valid_duration():
    data = copy.deepcopy(raw(GCP_FILE))
    del persona(data, "sre-oncall")["max_request_duration"]
    persona(data, "network-admin")["max_request_duration"] = "4 hours"
    found = codes(data, "gcp")
    assert {"MISSING_DURATION", "INVALID_DURATION"} <= found


def test_group_naming_pattern():
    az = copy.deepcopy(raw(AZURE_FILE))
    persona(az, "finops")["assignments"][0]["group"] = "FinOps Team"
    assert "GROUP_NAMING" in codes(az, "azure")
    gcp = copy.deepcopy(raw(GCP_FILE))
    persona(gcp, "finops")["assignments"][0]["group"] = "FinOps@example.com"
    assert "GROUP_NAMING" in codes(gcp, "gcp")


def test_unknown_scope_and_root_scope_opt_in():
    data = copy.deepcopy(raw(AZURE_FILE))
    dev = persona(data, "developer")
    dev["assignments"][0]["scopes"] = ["root", "landing-zones-qa"]
    found = codes(data, "azure")
    assert {"UNKNOWN_SCOPE", "ROOT_SCOPE_ACCESS"} <= found


def test_gcp_organization_scope_needs_opt_in():
    data = copy.deepcopy(raw(GCP_FILE))
    persona(data, "read-only")["assignments"][0]["scopes"] = ["organization"]
    assert "ROOT_SCOPE_ACCESS" in codes(data, "gcp")


@pytest.mark.parametrize(
    ("cloud", "path", "role", "standing"),
    [("azure", AZURE_FILE, "Contributor", "active"), ("gcp", GCP_FILE, "roles/editor", "binding")],
)
def test_broad_role_never_standing_in_prod(cloud, path, role, standing):
    data = copy.deepcopy(raw(path))
    pe = persona(data, "platform-engineer")
    pe["roles"] = [role]
    pe["assignment"] = standing
    pe.pop("activation_duration", None)
    pe.pop("max_request_duration", None)
    assert "STANDING_BROAD_ROLE_IN_PROD" in codes(data, cloud)


def test_gcp_basic_and_malformed_roles():
    data = copy.deepcopy(raw(GCP_FILE))
    persona(data, "developer")["roles"] = ["roles/editor", "compute.admin"]
    found = {(f.code, f.severity) for f in lint_cloud_model(parse_cloud_model(data, "gcp"))}
    assert ("BASIC_ROLE", "warning") in found
    assert ("INVALID_ROLE", "error") in found


def test_invalid_assignment_type_and_duplicates():
    data = copy.deepcopy(raw(AZURE_FILE))
    persona(data, "finops")["assignment"] = "permanent"
    data["personas"].append(copy.deepcopy(persona(data, "read-only")))
    found = codes(data, "azure")
    assert {"INVALID_ASSIGNMENT_TYPE", "DUPLICATE_PERSONA"} <= found


def test_summary_is_invalid_on_errors_but_not_warnings():
    data = copy.deepcopy(raw(AZURE_FILE))
    persona(data, "developer")["activation_duration"] = "PT1H"  # ignored on active → warning only
    summary = lint_cloud_summary(parse_cloud_model(data, "azure"))
    assert summary["valid"] is True
    assert [f["code"] for f in summary["findings"]] == ["DURATION_IGNORED"]
    persona(data, "developer")["roles"].append("Owner")
    assert lint_cloud_summary(parse_cloud_model(data, "azure"))["valid"] is False


# ----------------------------------------------------------------------------- cross-cloud matrix
def test_matrix_flags_persona_missing_in_a_cloud():
    aws = load_model(AWS_FILE)
    azure = load_cloud_model("azure", AZURE_FILE)
    gcp_data = copy.deepcopy(raw(GCP_FILE))
    gcp_data["personas"] = [p for p in gcp_data["personas"] if p["name"] != "finops"]
    matrix = persona_matrix(aws, azure, parse_cloud_model(gcp_data, "gcp"))
    row = next(r for r in matrix["personas"] if r["persona"] == "finops")
    assert row["missing"] == ["gcp"] and row["gcp"] is None
    assert matrix["consistent"] is False
    assert {(f["code"], f["cloud"], f["persona"]) for f in matrix["findings"]} == {
        ("PERSONA_MISSING", "gcp", "finops")
    }


def test_matrix_flags_privilege_mismatch():
    az_data = copy.deepcopy(raw(AZURE_FILE))
    persona(az_data, "break-glass")["privileged"] = False
    matrix = persona_matrix(load_model(AWS_FILE), parse_cloud_model(az_data, "azure"), None)
    assert matrix["clouds"] == ["aws", "azure"]
    assert any(
        f["code"] == "PRIVILEGE_MISMATCH" and f["persona"] == "break-glass" for f in matrix["findings"]
    )


def test_matrix_with_only_some_clouds_and_extra_persona():
    gcp_data = copy.deepcopy(raw(GCP_FILE))
    gcp_data["personas"].append(
        {
            "name": "data-scientist",
            "roles": ["roles/bigquery.dataViewer"],
            "assignment": "binding",
            "assignments": [{"group": "gcp-data-science@${domain}", "scopes": ["sandbox"]}],
        }
    )
    matrix = persona_matrix(
        azure=load_cloud_model("azure", AZURE_FILE), gcp=parse_cloud_model(gcp_data, "gcp")
    )
    row = next(r for r in matrix["personas"] if r["persona"] == "data-scientist")
    assert "aws" not in row and row["missing"] == ["azure"]
    assert persona_matrix()["personas"] == []


# ----------------------------------------------------------------------------- terraform wiring
def test_terraform_roots_read_the_models():
    az_live = (ROOT / "deploy/terraform/live/azure/governance/main.tf").read_text()
    gcp_live = (ROOT / "deploy/terraform/live/gcp/org/main.tf").read_text()
    assert "azure-access-model.yaml" in az_live and "yamldecode" in az_live
    assert "gcp-access-model.yaml" in gcp_live and "yamldecode" in gcp_live
    # Groups are looked up, never created: AD / Entra Connect / GCDS stay the source of truth.
    az_tf = "".join(p.read_text() for p in AZURE_MODULE.glob("*.tf"))
    gcp_tf = "".join(p.read_text() for p in GCP_MODULE.glob("*.tf"))
    assert 'data "azuread_group"' in az_tf and 'resource "azuread_group"' not in az_tf
    assert "azurerm_pim_eligible_role_assignment" in az_tf
    assert 'resource "google_cloud_identity_group"' not in gcp_tf
    assert "google_iam_deny_policy" in gcp_tf


def test_model_scopes_match_terraform_hierarchy():
    az_tf = (AZURE_MODULE / "main.tf").read_text()
    gcp_tf = (GCP_MODULE / "main.tf").read_text()
    for scope in raw(AZURE_FILE)["scopes"]:
        assert f'"{scope}"' in az_tf, scope
    for scope in raw(GCP_FILE)["scopes"]:
        assert f'"{scope}"' in gcp_tf, scope
