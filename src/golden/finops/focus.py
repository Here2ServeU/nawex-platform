"""FOCUS 1.x cost data — loader, normalizer and sample generator.

FOCUS (FinOps Open Cost and Usage Specification) gives every cloud bill the same columns. AWS Data
Exports (``FOCUS_1_0_AWS``), Azure Cost Management (``FocusCost``) and Google's BigQuery FOCUS view emit it
natively; older exports (AWS CUR legacy, Azure amortized/actual, GCP detailed billing export) are mapped
onto the same columns here through :data:`ALIASES`, so the rest of :mod:`golden.finops` only ever sees
FOCUS.

The normalized frame has the columns in :data:`FOCUS_COLUMNS`; ``ChargePeriodStart`` is a timezone-naive
``datetime64``, the cost columns are floats and ``Tags`` holds parsed ``dict[str, str]`` values.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

FOCUS_COLUMNS = (
    "BilledCost",
    "EffectiveCost",
    "ListCost",
    "ChargePeriodStart",
    "ServiceName",
    "ServiceCategory",
    "ProviderName",
    "SubAccountId",
    "RegionId",
    "ResourceId",
    "Tags",
)
COST_COLUMNS = ("BilledCost", "EffectiveCost", "ListCost")

# Native export column -> FOCUS column (matched case-insensitively, first hit wins).
ALIASES: dict[str, tuple[str, ...]] = {
    "BilledCost": (
        "billedcost",
        "line_item_unblended_cost",  # AWS CUR legacy
        "lineitem/unblendedcost",
        "costinbillingcurrency",  # Azure actual/amortized
        "cost",  # GCP billing export
    ),
    "EffectiveCost": (
        "effectivecost",
        "line_item_net_unblended_cost",
        "amortizedcost",
    ),
    "ListCost": (
        "listcost",
        "pricing_public_on_demand_cost",
        "pricing/publicondemandcost",
        "paygcostinbillingcurrency",
        "cost_at_list",
    ),
    "ChargePeriodStart": (
        "chargeperiodstart",
        "line_item_usage_start_date",
        "lineitem/usagestartdate",
        "date",
        "usagedatetime",
        "usage_start_time",
    ),
    "ServiceName": (
        "servicename",
        "product_product_name",
        "product/productname",
        "line_item_product_code",
        "metercategory",
        "service.description",
        "service_description",
    ),
    "ServiceCategory": ("servicecategory",),
    "ProviderName": ("providername", "provider", "cloud"),
    "SubAccountId": (
        "subaccountid",
        "line_item_usage_account_id",
        "lineitem/usageaccountid",
        "subscriptionid",
        "subscriptionguid",
        "project.id",
        "project_id",
    ),
    "RegionId": (
        "regionid",
        "product_region_code",
        "product_region",
        "product/region",
        "resourcelocation",
        "location.region",
        "location_region",
    ),
    "ResourceId": (
        "resourceid",
        "line_item_resource_id",
        "lineitem/resourceid",
        "instanceid",
        "resource.global_name",
        "resource_global_name",
    ),
    "Tags": ("tags", "resource_tags", "labels"),
}

# Which native columns identify which provider when ProviderName is absent.
PROVIDER_HINTS = {
    "AWS": ("line_item_unblended_cost", "lineitem/unblendedcost", "line_item_usage_account_id"),
    "Microsoft": ("costinbillingcurrency", "metercategory", "subscriptionid", "subscriptionguid"),
    "Google Cloud": ("service.description", "service_description", "project.id", "usage_start_time"),
}

# Keyword -> FOCUS ServiceCategory, used when an export lacks the column.
CATEGORY_KEYWORDS = (
    (
        "Networking",
        ("vpc", "nat", "network", "load balanc", "cloudfront", "cdn", "dns", "bandwidth", "transit"),
    ),
    ("Storage", ("s3", "storage", "ebs", "disk", "efs", "blob", "glacier", "backup", "snapshot")),
    (
        "Databases",
        ("rds", "aurora", "dynamo", "sql", "cosmos", "redis", "elasticache", "spanner", "bigtable"),
    ),
    (
        "AI and Machine Learning",
        ("sagemaker", "bedrock", "vertex", "openai", "machine learning", "cognitive"),
    ),
    ("Analytics", ("bigquery", "athena", "redshift", "glue", "kinesis", "synapse", "dataproc", "emr")),
    (
        "Management and Governance",
        ("cloudwatch", "monitor", "logging", "log analytics", "config", "cloudtrail", "observability"),
    ),
    ("Security", ("guardduty", "kms", "key vault", "security", "waf", "shield", "secret")),
    (
        "Compute",
        ("ec2", "compute", "virtual machine", "lambda", "function", "kubernetes", "eks", "aks", "gke"),
    ),
)


def parse_tags(value: Any) -> dict[str, str]:
    """Parse a tag/label cell from any provider into ``{key: value}``.

    Accepts a dict, FOCUS/CUR 2.0 JSON objects, Azure's brace-less ``"k": "v","k2": "v2"`` form,
    GCP's ``[{"key": ..., "value": ...}]`` list, and ``k=v;k2=v2`` strings. Empty or unparsable cells
    become ``{}`` — untagged.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(k): "" if v is None else str(v) for k, v in value.items()}
    if isinstance(value, list):
        out: dict[str, str] = {}
        for item in value:
            if isinstance(item, dict) and "key" in item:
                out[str(item["key"])] = "" if item.get("value") is None else str(item["value"])
        return out
    if isinstance(value, float) and np.isnan(value):
        return {}
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "{}"}:
        return {}
    for candidate in (text, "{" + text + "}"):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict | list):
            return parse_tags(parsed)
    pairs = [p for p in text.replace(",", ";").split(";") if "=" in p]
    return {k.strip(): v.strip() for k, v in (p.split("=", 1) for p in pairs)}


def infer_category(service: str) -> str:
    name = service.lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(k in name for k in keywords):
            return category
    return "Other"


def normalize_focus(frame: pd.DataFrame, provider: str | None = None) -> pd.DataFrame:
    """Map a raw export (FOCUS or native) onto :data:`FOCUS_COLUMNS`.

    Missing ``EffectiveCost`` falls back to ``BilledCost`` and missing ``ListCost`` to ``EffectiveCost``;
    ``ProviderName`` comes from the column, the ``provider`` argument, or the native column names.
    """
    lowered = {str(c).strip().lower(): c for c in frame.columns}
    out = pd.DataFrame(index=frame.index)
    for column, aliases in ALIASES.items():
        source = next((lowered[a] for a in aliases if a in lowered), None)
        if source is not None:
            out[column] = frame[source]

    if "BilledCost" not in out and "EffectiveCost" not in out:
        raise ValueError(
            "no cost column found; expected one of "
            f"{ALIASES['BilledCost'] + ALIASES['EffectiveCost']} (got {list(frame.columns)})"
        )
    if "ChargePeriodStart" not in out:
        raise ValueError(f"no charge date column found; expected one of {ALIASES['ChargePeriodStart']}")

    for column in COST_COLUMNS:
        if column in out:
            out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0).astype(float)
    if "BilledCost" not in out:
        out["BilledCost"] = out["EffectiveCost"]
    if "EffectiveCost" not in out:
        out["EffectiveCost"] = out["BilledCost"]
    if "ListCost" not in out:
        out["ListCost"] = out["EffectiveCost"]

    start = pd.to_datetime(out["ChargePeriodStart"], errors="coerce", utc=True, format="mixed")
    out["ChargePeriodStart"] = start.dt.tz_localize(None)
    out = out[out["ChargePeriodStart"].notna()].copy()

    if "ProviderName" not in out:
        hinted = provider or next(
            (name for name, hints in PROVIDER_HINTS.items() if any(h in lowered for h in hints)), "Unknown"
        )
        out["ProviderName"] = hinted
    for column in ("ServiceName", "SubAccountId", "RegionId", "ResourceId"):
        if column not in out:
            out[column] = ""
        out[column] = out[column].fillna("").astype(str)
    out["ProviderName"] = out["ProviderName"].fillna(provider or "Unknown").astype(str)
    if "ServiceCategory" not in out:
        out["ServiceCategory"] = out["ServiceName"].map(infer_category)
    out["ServiceCategory"] = out["ServiceCategory"].fillna("Other").astype(str)
    tags = out["Tags"] if "Tags" in out else pd.Series([None] * len(out), index=out.index)
    out["Tags"] = pd.Series([parse_tags(v) for v in tags], index=out.index, dtype=object)
    return out[list(FOCUS_COLUMNS)].reset_index(drop=True)


def load_focus(source: str | Path | pd.DataFrame, provider: str | None = None) -> pd.DataFrame:
    """Load FOCUS (or native, see :data:`ALIASES`) cost data from a CSV path, CSV text or a DataFrame."""
    if isinstance(source, pd.DataFrame):
        raw = source
    elif isinstance(source, Path) or (isinstance(source, str) and "\n" not in source):
        raw = pd.read_csv(Path(source), dtype=str, keep_default_na=False)
    else:
        raw = pd.read_csv(StringIO(source), dtype=str, keep_default_na=False)
    return normalize_focus(raw, provider=provider)


def to_focus_csv(frame: pd.DataFrame, path: str | Path | None = None) -> str:
    """Serialize a normalized frame back to FOCUS CSV (``Tags`` as JSON). Writes ``path`` when given."""
    out = frame.copy()
    out["Tags"] = [json.dumps(t, sort_keys=True) for t in out["Tags"]]
    out["ChargePeriodStart"] = out["ChargePeriodStart"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    text = out.to_csv(index=False)
    if path is not None:
        Path(path).write_text(text)
    return text


# ----------------------------------------------------------------------------- sample data
# (provider, sub-account, region, service, category, resource, team, daily cost, commitment discount)
# team None = untagged; "shared" = platform-wide shared services (networking, observability).
_CATALOG: tuple[tuple[str, str, str, str, str, str, str | None, float, float], ...] = (
    ("AWS", "111111111111", "us-east-1", "Amazon EC2", "Compute", "i-payments-api", "payments", 420.0, 0.28),
    ("AWS", "111111111111", "us-east-1", "Amazon RDS", "Databases", "db-payments", "payments", 180.0, 0.0),
    ("AWS", "111111111111", "us-east-1", "Amazon S3", "Storage", "payments-ledger", "payments", 35.0, 0.0),
    ("AWS", "222222222222", "us-east-1", "Amazon EKS", "Compute", "eks-search", "search", 95.0, 0.0),
    ("AWS", "222222222222", "us-east-1", "Amazon EC2", "Compute", "i-search-nodes", "search", 310.0, 0.28),
    (
        "AWS",
        "222222222222",
        "us-west-2",
        "Amazon OpenSearch Service",
        "Analytics",
        "os-search",
        "search",
        140.0,
        0.0,
    ),
    (
        "AWS",
        "333333333333",
        "us-east-1",
        "Amazon SageMaker",
        "AI and Machine Learning",
        "sm-train",
        "ml",
        260.0,
        0.0,
    ),
    ("AWS", "111111111111", "us-east-1", "Amazon VPC", "Networking", "nat-gw-shared", "shared", 120.0, 0.0),
    (
        "AWS",
        "111111111111",
        "us-east-1",
        "Amazon CloudWatch",
        "Management and Governance",
        "cw-shared",
        "shared",
        75.0,
        0.0,
    ),
    ("AWS", "222222222222", "us-east-1", "Amazon EC2", "Compute", "i-0orphan", None, 85.0, 0.0),
    ("AWS", "111111111111", "us-east-1", "Amazon EBS", "Storage", "vol-0unattached", None, 22.0, 0.0),
    (
        "Microsoft",
        "sub-data-001",
        "eastus",
        "Virtual Machines",
        "Compute",
        "vm-etl-01",
        "data-platform",
        210.0,
        0.0,
    ),
    ("Microsoft", "sub-data-001", "eastus", "Storage", "Storage", "stdatalake", "data-platform", 60.0, 0.0),
    (
        "Microsoft",
        "sub-data-001",
        "eastus",
        "Azure Database for PostgreSQL",
        "Databases",
        "pg-data",
        "data-platform",
        90.0,
        0.0,
    ),
    (
        "Microsoft",
        "sub-app-002",
        "eastus",
        "Azure Kubernetes Service",
        "Compute",
        "aks-payments",
        "payments",
        150.0,
        0.0,
    ),
    ("Microsoft", "sub-app-002", "eastus", "Virtual Network", "Networking", "vnet-hub", "shared", 40.0, 0.0),
    ("Microsoft", "sub-app-002", "eastus", "Virtual Machines", "Compute", "vm-legacy-jump", None, 30.0, 0.0),
    (
        "Google Cloud",
        "golden-ml-prod",
        "us-central1",
        "Vertex AI",
        "AI and Machine Learning",
        "vertex-endpoint",
        "ml",
        190.0,
        0.0,
    ),
    (
        "Google Cloud",
        "golden-ml-prod",
        "us-central1",
        "Compute Engine",
        "Compute",
        "gpu-train-pool",
        "ml",
        330.0,
        0.2,
    ),
    (
        "Google Cloud",
        "golden-data-prod",
        "us-central1",
        "BigQuery",
        "Analytics",
        "bq-warehouse",
        "data-platform",
        125.0,
        0.0,
    ),
    (
        "Google Cloud",
        "golden-data-prod",
        "us-central1",
        "Cloud Storage",
        "Storage",
        "gcs-raw",
        "data-platform",
        28.0,
        0.0,
    ),
    (
        "Google Cloud",
        "golden-ml-prod",
        "us-central1",
        "Cloud Logging",
        "Management and Governance",
        "logging-shared",
        "shared",
        33.0,
        0.0,
    ),
    (
        "Google Cloud",
        "golden-data-prod",
        "us-central1",
        "Compute Engine",
        "Compute",
        "vm-test-forgotten",
        None,
        18.0,
        0.0,
    ),
)

SAMPLE_COST_CENTERS = {
    "payments": "cc-1001",
    "search": "cc-1002",
    "ml": "cc-1003",
    "data-platform": "cc-1004",
}


def sample_focus_data(
    start: date = date(2026, 9, 1),
    days: int = 30,
    seed: int = 7,
    anomaly_day: int | None = 21,
    anomaly_resource: str = "i-payments-api",
    anomaly_factor: float = 4.0,
) -> pd.DataFrame:
    """Deterministic multi-cloud FOCUS sample: 3 providers, 4 teams + shared services, ~5% untagged spend.

    Costs grow ~0.3%/day with a weekend dip on compute and ±4% noise. On ``anomaly_day`` (0-based) the
    ``anomaly_resource`` costs ``anomaly_factor`` x normal — the spike :func:`detect_anomalies` should find.
    """
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        growth = 1.0 + 0.003 * offset
        weekend = day.weekday() >= 5
        for provider, account, region, service, category, resource, team, daily, discount in _CATALOG:
            factor = growth * float(rng.normal(1.0, 0.04))
            if weekend and category == "Compute":
                factor *= 0.9
            if anomaly_day is not None and offset == anomaly_day and resource == anomaly_resource:
                factor *= anomaly_factor
            effective = round(daily * factor, 4)
            tags: dict[str, str] = {}
            if team is not None:
                tags = {
                    "Project": "golden",
                    "Environment": "prod",
                    "Team": team,
                    "CostCenter": SAMPLE_COST_CENTERS.get(team, "cc-0000"),
                    "Owner": f"{team}@example.com",
                }
                if provider == "Google Cloud":
                    tags = {
                        "project": "golden",
                        "environment": "prod",
                        "team": team,
                        "cost_center": tags["CostCenter"],
                        "owner": team,
                    }
            rows.append(
                {
                    "BilledCost": effective,
                    "EffectiveCost": effective,
                    "ListCost": round(effective / (1.0 - discount), 4),
                    "ChargePeriodStart": pd.Timestamp(day),
                    "ServiceName": service,
                    "ServiceCategory": category,
                    "ProviderName": provider,
                    "SubAccountId": account,
                    "RegionId": region,
                    "ResourceId": resource,
                    "Tags": tags,
                }
            )
    return pd.DataFrame(rows, columns=list(FOCUS_COLUMNS))
