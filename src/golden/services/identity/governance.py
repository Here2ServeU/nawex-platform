"""Identity governance service — access-model lint, IAM role cleanup/consolidation, Wiz gap assessment."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from prometheus_client import Gauge
from pydantic import BaseModel, Field

from golden.identity import (
    AccessModel,
    analyze_authorization_details,
    assess_gaps,
    catalog,
    lint_summary,
    load_model,
    parse_model,
    sample_authorization_details,
    sample_findings,
)
from golden.identity.wiz import normalize
from golden.services.common import create_app, run

SERVICE = "identity-governance"
ROLES_BY_DISPOSITION = Gauge(
    "golden_identity_roles_total", "IAM roles in the latest analysis by disposition.", ["disposition"]
)
ROLE_FINDINGS = Gauge("golden_identity_role_findings_total", "IAM role findings by code.", ["code"])
BOUNDARY_COVERAGE = Gauge(
    "golden_identity_boundary_coverage_ratio", "Customer roles carrying a permission boundary."
)
IAM_USERS = Gauge("golden_identity_iam_users_total", "IAM users found (should trend to zero).")
CONTROL_STATUS = Gauge(
    "golden_identity_controls_total", "Identity controls by gap-assessment status.", ["status"]
)
POSTURE = Gauge(
    "golden_identity_posture_score", "Identity posture score from the latest Wiz gap assessment (0-100)."
)

app = create_app(
    SERVICE, "AWS IAM modernization: personas, role cleanup, control placement and Wiz gap assessment."
)
MAX_ACCOUNTS = 500
MAX_FINDINGS = 50_000


class AuthorizationDetailsIn(BaseModel):
    accounts: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=MAX_ACCOUNTS,
        description='[{"account_id": "...", "details": <aws iam get-account-authorization-details>}]',
    )
    unused_days: int = Field(90, ge=7, le=730)
    org_accounts: list[str] = Field(default_factory=list, max_length=10_000)
    access_model: dict[str, Any] | None = None


class FindingsIn(BaseModel):
    findings: list[dict[str, Any]] = Field(..., min_length=1, max_length=MAX_FINDINGS)


class AccessModelIn(BaseModel):
    model: dict[str, Any]


def _parse(raw: dict[str, Any]) -> AccessModel:
    try:
        return parse_model(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid access model: {exc}") from exc


def _model(raw: dict[str, Any] | None) -> AccessModel | None:
    """The posted model, else the configured one (GOLDEN_ACCESS_MODEL), else none."""
    if raw is not None:
        return _parse(raw)
    try:
        return load_model()
    except FileNotFoundError:
        return None


@app.get("/api/v1/identity/access-model")
def access_model() -> dict:
    model = _model(None)
    if model is None:
        raise HTTPException(status_code=404, detail="no access model configured (GOLDEN_ACCESS_MODEL)")
    return {"model": model.to_dict(), "lint": lint_summary(model)}


@app.post("/api/v1/identity/access-model/lint")
def lint(body: AccessModelIn) -> dict:
    return lint_summary(_parse(body.model))


@app.get("/api/v1/identity/controls")
def controls() -> dict:
    return {"controls": catalog()}


@app.get("/api/v1/identity/sample-authorization-details")
def sample_details() -> dict:
    return {"accounts": sample_authorization_details(now=datetime.now(UTC))}


@app.post("/api/v1/identity/roles/analyze")
def analyze_roles(body: AuthorizationDetailsIn) -> dict:
    try:
        result = analyze_authorization_details(
            body.accounts,
            unused_days=body.unused_days,
            org_accounts=set(body.org_accounts),
            model=_model(body.access_model),
        )
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid authorization details: {exc}") from exc
    summary = result["summary"]
    ROLES_BY_DISPOSITION.clear()
    for disposition, n in summary["by_disposition"].items():
        ROLES_BY_DISPOSITION.labels(disposition=disposition).set(n)
    ROLE_FINDINGS.clear()
    for code, n in summary["top_findings"]:
        ROLE_FINDINGS.labels(code=code).set(n)
    BOUNDARY_COVERAGE.set(summary["boundary_coverage_pct"] / 100)
    IAM_USERS.set(summary["iam_users"])
    return result


@app.get("/api/v1/identity/sample-findings")
def sample_wiz() -> dict:
    return {"findings": [f.to_dict() for f in sample_findings()]}


@app.post("/api/v1/identity/gap-assessment")
def gap_assessment(body: FindingsIn) -> dict:
    try:
        findings = [normalize(f, i) for i, f in enumerate(body.findings)]
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid finding: {exc}") from exc
    result = assess_gaps(findings)
    summary = result["summary"]
    for status, key in (("effective", "effective"), ("partial", "partial"), ("gap", "gaps")):
        CONTROL_STATUS.labels(status=status).set(summary[key])
    POSTURE.set(summary["identity_posture_score"])
    return result


def main() -> None:
    run(app, int(os.getenv("PORT", "8098")))


if __name__ == "__main__":
    main()
