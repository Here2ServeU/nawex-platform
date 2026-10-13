"""Application portfolio rationalization with the 7 Rs and the TIME model.

Every application gets a **disposition** (Retire, Retain, Rehost, Relocate, Replatform, Repurchase,
Refactor), a target platform, an effort T-shirt size, an estimated run-cost delta and a TIME quadrant
(Tolerate / Invest / Migrate / Eliminate). Decisions are rule-based and explainable: each result
carries the ``rule`` that fired and ``rationale`` lines a reviewer can challenge.

Rules are evaluated in order and the first match wins (documented in
``docs/modernization/portfolio-7rs.md``):

====  ===========  ==========================================================================================
#     Disposition  Condition
====  ===========  ==========================================================================================
R1    Retire       no active users, or business value 1 with technical health <= 2 and nothing depends on it
                   (a ``legal-hold``/``regulatory-hold`` tag turns this into Retain + archive)
R2    Retain       compliance hold, already SaaS / cloud-native, or mainframe without a refactor case
R3    Repurchase   a SaaS alternative exists and the app is COTS or not differentiating (business value <= 3)
R4    Refactor     strategic (business value >= 4) and changes often, but not already cloud-native
R5    Replatform   containerized, stateless / 12-factor, or a container-friendly runtime
R6    Relocate     on VMware and every rehost blocker is hypervisor-coupled (RDM, shared/independent disk,
                   VM encryption) and the app is high / mission critical, or licensing is VMware-bound
R7    Rehost       on VMware / physical with no blocked VM → OpenShift Virtualization via MTV
R8    Retain       fallback: rehost blocked and no other route — remediate blockers first
====  ===========  ==========================================================================================

VM assessment results (:class:`~golden.migration.assessment.VMAssessment`) feed R5–R8: a *blocked* VM makes
rehost infeasible and pushes the app to replatform (if the runtime allows), relocate or retain.

Cost figures are planning heuristics (see ``COST_DELTA_PCT`` and ``ONE_TIME_COST``), not quotes.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from golden.migration.assessment import VMAssessment

DISPOSITIONS = ("retire", "retain", "rehost", "relocate", "replatform", "repurchase", "refactor")
SIZES = ("XS", "S", "M", "L", "XL")
CRITICALITIES = ("low", "medium", "high", "mission_critical")

# Runtimes that run well in Linux containers with modest change (R5).
CONTAINER_RUNTIMES = {
    "node",
    "python",
    "go",
    "java-springboot",
    "java-tomcat",
    "java-weblogic",
    "java-websphere",
    "java-jboss",
    "dotnet-core",
    "php",
    "ruby",
}
# Blockers a hypervisor-compatible relocation (same VMware stack, new location) keeps working (R6).
RELOCATE_BLOCKERS = {"RDM_PHYSICAL", "SHARED_DISK", "INDEPENDENT_DISK", "ENCRYPTED_VM"}
HOLD_TAGS = {"legal-hold", "regulatory-hold"}
REGULATED_TAGS = {"pci", "pci-dss", "hipaa", "sox", "gdpr", "fedramp"}

# Base effort per disposition before adjustments.
BASE_EFFORT = {
    "retire": "XS",
    "retain": "XS",
    "rehost": "S",
    "relocate": "S",
    "replatform": "M",
    "repurchase": "M",
    "refactor": "L",
}
# Estimated change in annual run cost, as a fraction of today's annual cost (planning heuristic):
# rehost saves hypervisor licences; replatform adds density and managed services; refactor removes
# commercial middleware; repurchase swaps infra+ops for subscription fees.
COST_DELTA_PCT = {
    "retire": -1.0,
    "retain": 0.0,
    "rehost": -0.15,
    "relocate": -0.05,
    "replatform": -0.30,
    "repurchase": -0.20,
    "refactor": -0.40,
}
# One-time migration cost per effort size (USD, planning heuristic).
ONE_TIME_COST = {"XS": 10_000, "S": 25_000, "M": 75_000, "L": 200_000, "XL": 500_000}

TARGET_PLATFORM = {
    "retire": "Decommission (archive data to S3 Glacier / records system)",
    "retain": "Current platform (revisit next planning cycle)",
    "rehost": "OpenShift Virtualization (rehost via MTV)",
    "relocate": "VMware Cloud Foundation / VMware Cloud on AWS (hypervisor-compatible relocation)",
    "replatform": "OpenShift containers / EKS",
    "repurchase": "SaaS",
    "refactor": "Cloud-native services on EKS / OpenShift (managed data, event-driven)",
}
REPLATFORM_TARGETS = {
    "java-weblogic": "OpenShift containers (JBoss EAP / Open Liberty) / EKS",
    "java-websphere": "OpenShift containers (Open Liberty) / EKS",
    "dotnet-core": "OpenShift containers / EKS (Linux .NET)",
}
# Managed data target suggested alongside replatform / refactor (see golden.migration.database).
DATA_TARGETS = {
    "oracle": "Amazon RDS for Oracle (BYOL) or Aurora PostgreSQL (heterogeneous)",
    "sqlserver": "Amazon RDS for SQL Server or Aurora PostgreSQL (Babelfish)",
    "mysql": "Amazon Aurora MySQL",
    "mariadb": "Amazon Aurora MySQL",
    "postgresql": "Amazon Aurora PostgreSQL or Crunchy Postgres on OpenShift",
    "db2": "Aurora PostgreSQL (heterogeneous) or retain Db2",
    "mongodb": "Amazon DocumentDB or MongoDB Atlas",
}


@dataclass
class Application:
    name: str
    owner: str = ""
    business_criticality: str = "medium"  # low | medium | high | mission_critical
    business_value: int = 3  # 1 (commodity) .. 5 (differentiating)
    technical_health: int = 3  # 1 (failing) .. 5 (modern, well maintained)
    annual_cost: float = 0.0  # USD run cost: infra + licences + support
    users: int = 0  # active users (or calling systems for APIs)
    tech_stack: str = ""  # e.g. java-weblogic, dotnet-framework, node, cobol-cics, cots
    os: str = ""
    db_engine: str = ""  # oracle | sqlserver | mysql | postgresql | db2 | ... | "" (none)
    licensing: str = ""  # e.g. oracle-processor, commercial, open-source, vmware-bound, saas
    compliance: list[str] = field(default_factory=list)  # pci, hipaa, sox, legal-hold, ...
    dependencies: list[str] = field(default_factory=list)  # applications this app calls
    saas_alternative: bool = False
    change_frequency: str = "medium"  # low | medium | high (release cadence)
    stateless: bool = False
    twelve_factor: bool = False
    containerized: bool = False
    cots: bool = False  # commercial off-the-shelf product
    hosting: str = "vmware"  # vmware | physical | mainframe | saas | cloud
    vms: list[str] = field(default_factory=list)  # VM names in the vSphere inventory

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Application:
        return cls(**dict(data))

    @property
    def cloud_native(self) -> bool:
        return self.containerized and self.stateless and self.twelve_factor


@dataclass
class Disposition:
    application: str
    disposition: str  # one of DISPOSITIONS
    rule: str  # R1..R8
    target_platform: str
    data_target: str
    time_quadrant: str  # tolerate | invest | migrate | eliminate
    effort: str  # XS..XL
    annual_cost: float
    annual_cost_delta: float  # negative = savings
    one_time_cost: float
    rehost_feasible: bool | None  # None when no VM assessment is linked
    blocked_vms: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ----------------------------------------------------------------------------- TIME model
def time_quadrant(app: Application) -> str:
    """Gartner TIME: business value (y) vs technical health (x), split at 3 on a 1–5 scale."""
    high_value = app.business_value >= 3
    healthy = app.technical_health >= 3
    if high_value and healthy:
        return "invest"
    if high_value:
        return "migrate"
    if healthy:
        return "tolerate"
    return "eliminate"


# ----------------------------------------------------------------------------- helpers
def _size(base: str, bump: int) -> str:
    return SIZES[min(len(SIZES) - 1, SIZES.index(base) + max(0, bump))]


def _index_assessments(
    assessments: Iterable[VMAssessment] | Mapping[str, VMAssessment] | None,
) -> dict[str, VMAssessment]:
    if assessments is None:
        return {}
    if isinstance(assessments, Mapping):
        return dict(assessments)
    return {a.vm: a for a in assessments}


def _linked(app: Application, by_vm: dict[str, VMAssessment]) -> list[VMAssessment]:
    if app.vms:
        return [by_vm[v] for v in app.vms if v in by_vm]
    return [a for a in by_vm.values() if a.application == app.name]


def _dependents(apps: Iterable[Application]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for a in apps:
        for dep in a.dependencies:
            out.setdefault(dep, set()).add(a.name)
    return out


# ----------------------------------------------------------------------------- decision rules
def decide(
    app: Application,
    *,
    vm_assessments: Iterable[VMAssessment] | Mapping[str, VMAssessment] | None = None,
    dependents: Iterable[str] = (),
) -> Disposition:
    """Apply rules R1–R8 to one application. ``dependents`` are apps that call this one."""
    by_vm = _index_assessments(vm_assessments)
    linked = _linked(app, by_vm)
    blocked = [a for a in linked if a.readiness == "blocked"]
    blocker_codes = {f.code for a in blocked for f in a.findings if f.severity == "blocker"}
    rehost_feasible: bool | None = (not blocked) if linked else None
    dependents = sorted(set(dependents))
    tags = {t.lower() for t in app.compliance}
    stack = app.tech_stack.lower()
    hosting = app.hosting.lower()
    why: list[str] = []
    target = ""

    def done(disposition: str, rule: str) -> Disposition:
        return _finalize(app, disposition, rule, target, why, rehost_feasible, blocked, dependents)

    # R1 Retire ----------------------------------------------------------------
    unused = app.users <= 0
    low_value_orphan = app.business_value <= 1 and app.technical_health <= 2 and not dependents
    if unused or low_value_orphan:
        reason = (
            "no active users"
            if unused
            else f"business value {app.business_value}/5 and technical health {app.technical_health}/5 with no dependents"
        )
        if tags & HOLD_TAGS:
            why += [
                f"Retire candidate ({reason}) but under {', '.join(sorted(tags & HOLD_TAGS))}",
                "Retain read-only until the hold expires; archive data and shut down write paths",
            ]
            target = "Current platform, read-only (archive when hold expires)"
            return done("retain", "R1")
        why.append(f"Retire: {reason}")
        if dependents:
            why.append(f"Re-point or stub callers first: {', '.join(dependents)}")
        why.append("Archive data per retention policy, then decommission infrastructure and licences")
        return done("retire", "R1")

    # R2 Retain ----------------------------------------------------------------
    mainframe_refactor = hosting == "mainframe" and app.business_value >= 4 and app.change_frequency == "high"
    if tags & HOLD_TAGS:
        why.append(f"Compliance hold ({', '.join(sorted(tags & HOLD_TAGS))}) prevents changing the platform")
        return done("retain", "R2")
    if hosting == "saas":
        why.append("Already consumed as SaaS; keep and manage through vendor governance")
        target = "Existing SaaS"
        return done("retain", "R2")
    if hosting == "cloud" and app.cloud_native:
        why.append("Already cloud-native (containerized, stateless, 12-factor) on cloud hosting")
        target = "Current cloud platform"
        return done("retain", "R2")
    if hosting == "mainframe" and not mainframe_refactor:
        why += [
            "Mainframe workload without a strong refactor case (needs value >= 4 and high change rate)",
            "Retain; expose via APIs (anti-corruption layer) and revisit with a strangler-fig plan",
        ]
        target = "Mainframe (retain), API-enabled"
        return done("retain", "R2")

    # R3 Repurchase ------------------------------------------------------------
    if app.saas_alternative and (app.cots or app.business_value <= 3):
        why.append(
            "SaaS alternative available and the app is "
            + ("COTS" if app.cots else f"not differentiating (business value {app.business_value}/5)")
        )
        why.append("Move to SaaS; migrate data and integrations, retire the on-prem install")
        return done("repurchase", "R3")

    # R4 Refactor --------------------------------------------------------------
    if app.business_value >= 4 and app.change_frequency == "high" and not app.cloud_native:
        why.append(
            f"Strategic (business value {app.business_value}/5) with high change frequency, "
            "not yet cloud-native"
        )
        if hosting == "mainframe":
            why.append("Mainframe refactor: strangle capabilities into services behind an API facade")
        else:
            why.append("Refactor incrementally (strangler fig) into services with managed data stores")
        return done("refactor", "R4")

    # R5 Replatform ------------------------------------------------------------
    container_friendly = (
        app.containerized or app.stateless or app.twelve_factor or stack in CONTAINER_RUNTIMES
    )
    if container_friendly:
        signals = [
            s
            for s, on in (
                ("containerized", app.containerized),
                ("stateless", app.stateless),
                ("12-factor", app.twelve_factor),
                (f"container-friendly runtime ({stack})", stack in CONTAINER_RUNTIMES),
            )
            if on
        ]
        why.append(f"Replatform: {', '.join(signals)}")
        if blocked:
            why.append(
                f"Rehost blocked on {', '.join(sorted(a.vm for a in blocked))} "
                f"({', '.join(sorted(blocker_codes))}); containerizing avoids the VM blockers"
            )
        target = REPLATFORM_TARGETS.get(stack, TARGET_PLATFORM["replatform"])
        return done("replatform", "R5")

    # R6 Relocate --------------------------------------------------------------
    critical = app.business_criticality in {"high", "mission_critical"}
    if hosting == "vmware" and (
        (blocked and blocker_codes <= RELOCATE_BLOCKERS and critical) or app.licensing == "vmware-bound"
    ):
        if app.licensing == "vmware-bound":
            why.append("Licensing is bound to the VMware hypervisor")
        else:
            why.append(
                f"Rehost blocked only by hypervisor-coupled features ({', '.join(sorted(blocker_codes))}) "
                f"on a {app.business_criticality} application"
            )
        why.append("Relocate to a VMware-compatible cloud now; re-assess for rehost/replatform later")
        return done("relocate", "R6")

    # R7 Rehost ----------------------------------------------------------------
    if hosting in {"vmware", "physical", ""} and not blocked:
        why.append(
            "No blocked VMs; lift-and-shift with MTV"
            if linked
            else "No VM assessment linked; default to rehost via MTV (assess VMs to confirm)"
        )
        if stack.startswith("dotnet-framework"):
            why.append(".NET Framework needs Windows; rehost the VM rather than containerize on Linux")
        return done("rehost", "R7")

    # R8 Retain (fallback) -----------------------------------------------------
    if blocked:
        why.append(
            f"Rehost blocked on {', '.join(sorted(a.vm for a in blocked))} ({', '.join(sorted(blocker_codes))}) "
            "and no container or relocation route"
        )
        why.append("Retain and remediate blockers (OS upgrade, device removal), then re-assess")
    else:
        why.append(f"No rule matched hosting '{app.hosting}'; retain pending review")
    return done("retain", "R8")


def _finalize(
    app: Application,
    disposition: str,
    rule: str,
    target: str,
    why: list[str],
    rehost_feasible: bool | None,
    blocked: list[VMAssessment],
    dependents: list[str],
) -> Disposition:
    tags = {t.lower() for t in app.compliance}
    bump = 0
    if disposition not in {"retire", "retain"}:
        if app.business_criticality == "mission_critical":
            bump += 1
            why.append("Effort +1: mission-critical (extra rehearsal and hypercare)")
        if len(app.dependencies) + len(dependents) >= 4:
            bump += 1
            why.append(f"Effort +1: {len(app.dependencies) + len(dependents)} integration dependencies")
        if tags & REGULATED_TAGS:
            bump += 1
            why.append(f"Effort +1: regulated ({', '.join(sorted(tags & REGULATED_TAGS))})")
    if disposition == "refactor" and app.hosting.lower() == "mainframe":
        bump += 1
    effort = _size(BASE_EFFORT[disposition], bump)
    delta = round(app.annual_cost * COST_DELTA_PCT[disposition], 2)
    data_target = ""
    if app.db_engine and disposition in {"replatform", "refactor"}:
        data_target = DATA_TARGETS.get(
            app.db_engine.lower(), "Managed database (assess with golden.migration.database)"
        )
    elif app.db_engine and disposition in {"rehost", "relocate"}:
        data_target = "Database moves with the VM (assess for a managed DB later)"
    return Disposition(
        application=app.name,
        disposition=disposition,
        rule=rule,
        target_platform=target or TARGET_PLATFORM[disposition],
        data_target=data_target,
        time_quadrant=time_quadrant(app),
        effort=effort,
        annual_cost=app.annual_cost,
        annual_cost_delta=delta,
        one_time_cost=float(ONE_TIME_COST[effort]) if disposition != "retain" else 0.0,
        rehost_feasible=rehost_feasible,
        blocked_vms=sorted(a.vm for a in blocked),
        rationale=why,
    )


# ----------------------------------------------------------------------------- portfolio
def assess_portfolio(
    apps: Iterable[Application],
    vm_assessments: Iterable[VMAssessment] | Mapping[str, VMAssessment] | None = None,
) -> dict[str, Any]:
    """Disposition every app and summarize the portfolio (counts, TIME, cost, effort)."""
    apps = list(apps)
    by_vm = _index_assessments(vm_assessments)
    dependents = _dependents(apps)
    results = [decide(a, vm_assessments=by_vm, dependents=dependents.get(a.name, ())) for a in apps]
    by_disp = Counter(r.disposition for r in results)
    total_cost = sum(r.annual_cost for r in results)
    savings = -sum(r.annual_cost_delta for r in results)
    one_time = sum(r.one_time_cost for r in results)
    return {
        "summary": {
            "applications": len(results),
            "dispositions": {d: by_disp.get(d, 0) for d in DISPOSITIONS},
            "time": dict(sorted(Counter(r.time_quadrant for r in results).items())),
            "effort": {s: sum(1 for r in results if r.effort == s) for s in SIZES},
            "annual_cost": round(total_cost, 2),
            "estimated_annual_savings": round(savings, 2),
            "estimated_one_time_cost": round(one_time, 2),
            "payback_months": round(one_time / (savings / 12), 1) if savings > 0 else None,
            "rehost_blocked": sorted(r.application for r in results if r.rehost_feasible is False),
        },
        "applications": [r.to_dict() for r in results],
    }


# ----------------------------------------------------------------------------- CSV loader
CSV_COLUMNS = (
    "name",
    "owner",
    "business_criticality",
    "business_value",
    "technical_health",
    "annual_cost",
    "users",
    "tech_stack",
    "os",
    "db_engine",
    "licensing",
    "compliance",
    "dependencies",
    "saas_alternative",
    "change_frequency",
    "stateless",
    "twelve_factor",
    "containerized",
    "cots",
    "hosting",
    "vms",
)
_LIST_COLS = {"compliance", "dependencies", "vms"}
_BOOL_COLS = {"saas_alternative", "stateless", "twelve_factor", "containerized", "cots"}
_INT_COLS = {"business_value", "technical_health", "users"}


def _bool(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "y", "1"}


def load_portfolio_csv(path: str | Path) -> list[Application]:
    """Load applications from CSV. Only ``name`` is required; see ``CSV_COLUMNS``.

    List columns (``compliance``, ``dependencies``, ``vms``) are ``;``-separated; booleans accept
    true/yes/y/1; ``business_value`` and ``technical_health`` are clamped to 1–5.
    """
    apps: list[Application] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            if not row.get("name"):
                continue
            kwargs: dict[str, Any] = {}
            for col in CSV_COLUMNS:
                raw = row.get(col, "")
                if raw == "":
                    continue
                if col in _LIST_COLS:
                    kwargs[col] = [x.strip() for x in raw.split(";") if x.strip()]
                elif col in _BOOL_COLS:
                    kwargs[col] = _bool(raw)
                elif col in _INT_COLS:
                    kwargs[col] = int(float(raw.replace(",", "")))
                elif col == "annual_cost":
                    kwargs[col] = float(raw.replace(",", "").replace("$", ""))
                elif col == "business_criticality":
                    kwargs[col] = raw.lower().replace("-", "_").replace(" ", "_")
                else:
                    kwargs[col] = raw
            for col in ("business_value", "technical_health"):
                if col in kwargs:
                    kwargs[col] = max(1, min(5, kwargs[col]))
            apps.append(Application(**kwargs))
    return apps


def write_portfolio_csv(path: str | Path, apps: Iterable[Application]) -> Path:
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(CSV_COLUMNS))
        w.writeheader()
        for a in apps:
            d = a.to_dict()
            w.writerow({c: ";".join(d[c]) if c in _LIST_COLS else d[c] for c in CSV_COLUMNS})
    return path


# ----------------------------------------------------------------------------- sample portfolio
def sample_portfolio() -> list[Application]:
    """~25 realistic applications covering every disposition; names in ``sample_inventory`` link to VMs."""
    A = Application
    return [
        # --- apps that exist in golden.migration.inventory.sample_inventory -------------------------
        A("erp", "finance-it", "high", 4, 3, 1_200_000, 1800, "sap-ecc", "RHEL 8", "oracle",
          "oracle-processor", ["sox"], ["hr-portal", "reporting"], False, "low", cots=True),
        A("crm", "sales-ops", "medium", 3, 3, 420_000, 650, "dotnet-framework", "Windows Server 2019",
          "sqlserver", "commercial", [], ["erp"], False, "medium"),
        A("hr-portal", "people-tech", "low", 2, 2, 180_000, 2400, "java-tomcat", "RHEL 8", "mysql",
          "open-source", ["gdpr"], [], True, "low", cots=True),
        A("file-services", "infra", "medium", 2, 3, 95_000, 3000, "windows-file-server",
          "Windows Server 2019", "", "commercial", [], [], False, "low"),
        A("reporting", "data-team", "low", 3, 2, 140_000, 120, "java-springboot", "CentOS 7", "oracle",
          "oracle-processor", [], ["erp"], False, "medium"),
        A("payments", "payments-eng", "mission_critical", 5, 3, 900_000, 250_000, "java-weblogic",
          "RHEL 8", "postgresql", "commercial", ["pci-dss"], ["fraud-scoring", "notifications-api"],
          False, "high"),
        A("legacy-mainframe-gw", "core-it", "high", 3, 1, 260_000, 40, "cobol-gateway",
          "Windows Server 2008 R2", "", "commercial", [], ["policy-admin"], False, "low"),
        # --- mainframe ---------------------------------------------------------------------------
        A("policy-admin", "core-it", "mission_critical", 5, 2, 2_400_000, 900, "cobol-cics", "z/OS",
          "db2", "mips", ["sox"], [], False, "low", hosting="mainframe"),
        A("claims-adjudication", "claims-it", "mission_critical", 5, 2, 1_600_000, 1200, "cobol-cics",
          "z/OS", "db2", "mips", ["hipaa"], ["policy-admin"], False, "high", hosting="mainframe"),
        # --- COTS / SaaS replaceable ---------------------------------------------------------------
        A("travel-expense", "finance-it", "low", 2, 2, 110_000, 5200, "cots", "Windows Server 2016",
          "sqlserver", "commercial", [], ["erp"], True, "low", cots=True),
        A("helpdesk", "it-ops", "medium", 2, 3, 85_000, 6000, "php", "Ubuntu 20.04", "mysql",
          "open-source", [], [], True, "low"),
        A("lms-training", "people-tech", "low", 2, 3, 60_000, 4800, "cots", "Windows Server 2016",
          "sqlserver", "commercial", [], ["hr-portal"], True, "low", cots=True),
        A("email-archive", "infra", "low", 1, 2, 70_000, 0, "cots", "Windows Server 2012 R2",
          "sqlserver", "commercial", ["legal-hold"], [], True, "low", cots=True),
        # --- legacy Java / .NET ---------------------------------------------------------------------
        A("claims-portal", "claims-it", "high", 4, 2, 380_000, 15_000, "java-weblogic", "RHEL 7",
          "oracle", "oracle-processor", ["hipaa"], ["claims-adjudication"], False, "medium"),
        A("broker-portal", "distribution-it", "high", 4, 3, 300_000, 3500, "java-websphere", "RHEL 8",
          "db2", "commercial", [], ["policy-admin"], False, "medium"),
        A("billing-engine", "finance-it", "high", 4, 3, 450_000, 60, "dotnet-framework",
          "Windows Server 2016", "sqlserver", "commercial", ["sox"], ["erp"], False, "low"),
        A("dealer-extranet", "distribution-it", "medium", 3, 2, 150_000, 800, "dotnet-framework",
          "Windows Server 2012 R2", "sqlserver", "commercial", [], [], False, "low"),
        # --- modern / stateless ---------------------------------------------------------------------
        A("notifications-api", "platform", "high", 3, 4, 90_000, 30, "node", "Ubuntu 22.04", "",
          "open-source", [], [], False, "high", stateless=True, twelve_factor=True, containerized=True),
        A("quote-api", "distribution-it", "high", 4, 4, 120_000, 40, "node", "Ubuntu 22.04",
          "postgresql", "open-source", [], ["policy-admin"], False, "medium", stateless=True,
          twelve_factor=True),
        A("fraud-scoring", "risk-analytics", "mission_critical", 5, 4, 260_000, 20, "python", "RHEL 9",
          "postgresql", "open-source", ["pci-dss"], [], False, "high", stateless=True,
          twelve_factor=True, containerized=True, hosting="cloud"),
        A("customer-mobile-bff", "digital", "high", 5, 3, 200_000, 180_000, "java-springboot",
          "RHEL 8", "", "open-source", [], ["quote-api", "payments", "broker-portal", "notifications-api"],
          False, "high"),
        # --- retire / retain edge cases ---------------------------------------------------------------
        A("intranet-legacy", "comms", "low", 1, 1, 45_000, 0, "php", "CentOS 6", "mysql",
          "open-source", [], [], False, "low"),
        A("fax-gateway", "it-ops", "low", 1, 2, 38_000, 15, "vb6", "Windows Server 2008 R2", "",
          "commercial", [], [], False, "low"),
        A("lab-instruments", "research", "high", 3, 2, 75_000, 25, "labview", "Windows 10", "",
          "vmware-bound", [], [], False, "low"),
        A("treasury-cms", "treasury", "high", 4, 3, 330_000, 90, "cots", "Windows Server 2019",
          "oracle", "commercial", ["sox"], ["erp"], False, "low", cots=True),
        A("office-suite", "it-ops", "medium", 2, 4, 400_000, 6500, "saas", "", "", "saas", [], [], True,
          "low", hosting="saas"),
    ]  # fmt: skip
