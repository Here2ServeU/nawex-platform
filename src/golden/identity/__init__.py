"""AWS identity governance domain: persona access model, role cleanup, control placement, Wiz gap assessment."""

from golden.identity.controls import CONTROLS, Control, catalog, match_controls
from golden.identity.model import AccessModel, Persona, lint_model, lint_summary, load_model, parse_model
from golden.identity.multicloud import (
    CloudAccessModel,
    lint_cloud_model,
    lint_cloud_summary,
    load_cloud_model,
    multicloud_summary,
    parse_cloud_model,
    persona_matrix,
)
from golden.identity.roles import (
    RoleAnalysis,
    analyze_authorization_details,
    analyze_role,
    sample_authorization_details,
)
from golden.identity.wiz import CloudFinding, assess_gaps, load_findings, sample_findings

__all__ = [
    "CloudAccessModel",
    "lint_cloud_model",
    "lint_cloud_summary",
    "load_cloud_model",
    "multicloud_summary",
    "parse_cloud_model",
    "persona_matrix",
    "CONTROLS",
    "AccessModel",
    "CloudFinding",
    "Control",
    "Persona",
    "RoleAnalysis",
    "analyze_authorization_details",
    "analyze_role",
    "assess_gaps",
    "catalog",
    "lint_model",
    "lint_summary",
    "load_findings",
    "load_model",
    "match_controls",
    "parse_model",
    "sample_authorization_details",
    "sample_findings",
]
