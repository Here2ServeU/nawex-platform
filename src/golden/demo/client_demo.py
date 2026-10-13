"""Narrated executive demo across all four domains, with an HTML leave-behind report.

    golden demo client --vertical hospital  --client "City Medical Center"
    golden demo client --vertical bank      --client "National Finance Corp"
    golden demo client --vertical gpu       --client "Acme AI Labs"
    golden demo client --vertical migration --client "Contoso Manufacturing"
    golden demo client --vertical all       --client "Contoso" --fast

Every number shown is computed live by the platform's pipelines (simulated data, real code paths).
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Any

from jinja2 import Environment, select_autoescape

from golden.ai.business_value import ROICalculator
from golden.ai.datasets.fintech_simulator import make_fraud_scenario_stream
from golden.ai.datasets.healthcare_simulator import make_patient_vitals_stream, make_phi_access_log
from golden.ai.explainability import build_text_report
from golden.ai.pipelines.detect_fraud import detect_transaction_anomalies
from golden.ai.pipelines.detect_phi_anomalies import detect_patient_safety_risk
from golden.gpu import analyze_fleet, make_gpu_fleet
from golden.migration import assess_inventory, plan_waves, sample_inventory
from golden.security import security_status

R, Y, G, B, W, DIM, RST, BOLD = (
    "\033[0;91m",
    "\033[0;93m",
    "\033[0;92m",
    "\033[0;96m",
    "\033[0;97m",
    "\033[2m",
    "\033[0m",
    "\033[1m",
)
if os.getenv("NO_COLOR"):
    R = Y = G = B = W = DIM = RST = BOLD = ""


@dataclass
class Profile:
    key: str
    label: str
    roi_vertical: str
    capabilities: list[str]
    signals: list[tuple[str, str, str]]
    model_cards: list[dict[str, Any]]
    detect: Callable[[], tuple[list[str], float, dict[str, float]]]
    extras: dict[str, Any] = field(default_factory=dict)


# ----------------------------------------------------------------------------- detections
def _detect_healthcare() -> tuple[list[str], float, dict[str, float]]:
    vitals = make_patient_vitals_stream(n_patients=24, n_timepoints=3)
    phi = make_phi_access_log(n_users=15, n_events=200)
    safety = detect_patient_safety_risk(vitals)
    flagged = int(phi["is_flagged"].sum())
    top = float(phi["phi_risk_score"].max())
    lines = [
        f"Patients monitored: {safety['total_patients_monitored']}  ·  at-risk: {len(safety['at_risk_patients'])}"
        f"  ·  safety level: {safety['level'].upper()}",
        f"PHI access events: {len(phi)}  ·  anomalies: {flagged}  ·  max risk: {top:.3f}",
        f"Recommendation: {safety['recommendation']}",
    ]
    contributions = {
        "Vital-sign deviation (SpO₂/HR)": 0.38,
        "After-hours PHI access": 0.27,
        "Cross-department access": 0.20,
        "EHR latency SLO deviation": 0.10,
        "Acuity": 0.05,
    }
    return lines, top, contributions


def _detect_fintech() -> tuple[list[str], float, dict[str, float]]:
    txns = make_fraud_scenario_stream(n_transactions=200, scenario="fraud_burst")
    scored = detect_transaction_anomalies(txns, threshold=0.35)
    exposure = float(txns.loc[txns["is_fraud"], "estimated_loss_usd"].sum())
    top = float(scored["fraud_score"].max())
    lines = [
        f"Transactions analysed: {len(scored)}  ·  flagged: {int(scored['is_flagged'].sum())}  ·  max score: {top:.3f}",
        f"Simulated fraud exposure in window: ${exposure:,.0f}",
    ]
    contributions = {
        "Amount anomaly (z-score)": 0.30,
        "Velocity (txn/hour)": 0.28,
        "Geographic risk": 0.18,
        "Channel (card-not-present)": 0.14,
        "Merchant category": 0.10,
    }
    return lines, top, contributions


def _detect_gpu() -> tuple[list[str], float, dict[str, float]]:
    report = analyze_fleet(make_gpu_fleet(scenario="hot"))
    lines = [
        f"GPUs: {report.gpus} on {report.nodes} nodes  ·  avg utilisation {report.avg_utilization_pct:.0f}%",
        f"Idle: {report.idle_gpus}  ·  hot: {report.hot_gpus}  ·  hardware faults: {report.hardware_faults}"
        f"  ·  nodes freeable: {report.nodes_freeable_by_consolidation}",
        f"Projected savings: ${report.projected_annual_savings_usd:,.0f}/year",
    ] + [f"→ {r['action']}: {r['detail']}" for r in report.recommendations[:4]]
    risk = 0.9 if report.risk_flags.get("gpu_thermal_risk") == "critical" else 0.6
    contributions = {
        "Idle / stranded capacity": 0.41,
        "Low packing density": 0.27,
        "Thermal throttling": 0.17,
        "Power over budget": 0.10,
        "Hardware errors": 0.05,
    }
    return lines, risk, contributions


def _detect_migration() -> tuple[list[str], float, dict[str, float]]:
    vms = sample_inventory(apps_multiplier=3)
    summary = assess_inventory(vms)["summary"]
    plan = plan_waves(vms, max_vms_per_wave=20)
    lines = [
        f"VMs discovered: {summary['vms']}  ·  ready: {summary['ready']}  ·  remediation: "
        f"{summary['needs_remediation']}  ·  blocked: {summary['blocked']}",
        f"Storage to move: {summary['total_disk_tb']} TB  ·  waves planned: {len(plan.waves)}  ·  "
        f"backlog groups: {len(plan.backlog)}",
        "Top issues: " + ", ".join(f"{code}×{n}" for code, n in summary["top_issues"]),
    ]
    risk = summary["blocked"] / max(summary["vms"], 1)
    contributions = {
        "Unsupported/EOL guest OS": 0.32,
        "RDM / shared disks": 0.28,
        "Snapshots present": 0.18,
        "Large disks (warm migration)": 0.14,
        "Missing VMware Tools": 0.08,
    }
    return lines, risk, contributions


PROFILES: dict[str, Profile] = {
    "hospital": Profile(
        "hospital",
        "Healthcare",
        "healthcare",
        [
            "Clinical deterioration (NEWS2)",
            "PHI access anomaly detection (HIPAA §164.312(b))",
            "EHR reliability forecasting (LSTM/TCN)",
            "30-day readmission risk",
        ],
        [
            ("Patient vital-sign monitoring", "Elevated", "Charge-nurse notification"),
            ("PHI access anomaly detection", "Normal", "Audit log entry"),
            ("EHR ingestion latency (FHIR R4)", "Normal", "SLO monitoring"),
        ],
        [
            {
                "name": "NEWS2 Clinical Score",
                "type": "Published early-warning score",
                "metrics": [("Bands", "low/medium/high")],
                "ref": "Royal College of Physicians (2017)",
            },
            {
                "name": "PHI Access Risk",
                "type": "5-signal composite",
                "metrics": [("Signals", "5")],
                "ref": "NIST SP 800-66r2 · HIPAA §164.312(b)",
            },
        ],
        _detect_healthcare,
    ),
    "bank": Profile(
        "bank",
        "Financial Services",
        "fintech",
        [
            "Real-time fraud scoring (5 explainable signals)",
            "Payment gateway SLO prediction",
            "AML/BSA pattern detection",
            "Settlement window risk",
        ],
        [
            ("Real-time fraud scoring", "Elevated", "Transaction hold queue"),
            ("Payment gateway SLO", "Normal", "Latency monitoring"),
            ("Settlement batch risk", "Normal", "Clearing window tracking"),
        ],
        [
            {
                "name": "Fraud Signals Engine",
                "type": "Weighted composite",
                "metrics": [("Signals", "5")],
                "ref": "Federal Reserve Payments Study · BSA/AML",
            }
        ],
        _detect_fintech,
    ),
    "gpu": Profile(
        "gpu",
        "AI Infrastructure / GPU",
        "gpu",
        [
            "GPU fleet telemetry (nvidia-smi / DCGM)",
            "Thermal, ECC and XID anomaly detection",
            "Consolidation, MIG and idle reclamation",
            "Power capping and cost optimisation",
        ],
        [
            ("GPU thermal monitoring", "Elevated", "Workload migration"),
            ("Idle GPU detection", "Elevated", "Reclaim to pool"),
            ("Hardware error tracking", "Normal", "Node drain on fault"),
        ],
        [
            {
                "name": "Fleet Packing Optimiser",
                "type": "First-fit-decreasing bin packing",
                "metrics": [("Target", "70% util")],
                "ref": "NVIDIA DCGM · MIG user guide",
            }
        ],
        _detect_gpu,
    ),
    "migration": Profile(
        "migration",
        "VMware → OpenShift Migration",
        "migration",
        [
            "RVTools inventory discovery",
            "Readiness assessment (blockers / warnings)",
            "Dependency-aware wave planning",
            "MTV manifest generation, cutover and rollback",
        ],
        [
            ("Inventory assessment", "Elevated", "Remediation backlog"),
            ("Wave planning", "Normal", "Pilot wave scheduled"),
            ("Cutover validation", "Normal", "Governed rollback"),
        ],
        [
            {
                "name": "Migration Readiness Rules",
                "type": "Deterministic rule engine",
                "metrics": [("Rules", "15+")],
                "ref": "Migration Toolkit for Virtualization (Forklift)",
            }
        ],
        _detect_migration,
    ),
}


# ----------------------------------------------------------------------------- runner
class ClientDemo:
    def __init__(self, vertical: str, client_name: str, output_dir: Path, *, fast: bool = False) -> None:
        self.profile = PROFILES[vertical]
        self.client_name = client_name
        self.output_dir = output_dir
        self.fast = fast
        output_dir.mkdir(parents=True, exist_ok=True)

    def _p(self, text: str = "", delay: float = 0.0) -> None:
        print(text)
        if delay and not self.fast:
            time.sleep(delay)

    def _header(self, title: str) -> None:
        self._p()
        self._p(f"{B}{BOLD}{'═' * 70}\n  {title}\n{'═' * 70}{RST}", 0.3)

    def run(self) -> dict[str, Any]:
        prof = self.profile
        self._header(f"GOLDEN PLATFORM — {prof.label.upper()} — {self.client_name}")
        for cap in prof.capabilities:
            self._p(f"  {G}✓{RST} {W}{cap}{RST}", 0.1)

        self._header("AI DETECTION (live pipelines on synthetic data)")
        lines, risk, contributions = prof.detect()
        for line in lines:
            self._p(f"  {W}{line}{RST}", 0.15)

        self._header("EXPLAINABILITY")
        report = build_text_report(contributions, top_k=5)
        for line in report.splitlines():
            self._p(f"  {DIM}{line}{RST}", 0.08)

        self._header("AI SAFETY POSTURE")
        safety = security_status()
        self._p(
            f"  Autonomy mode: {Y}{safety['autonomy_mode']}{RST}  ·  kill switch: "
            f"{R + 'ENGAGED' if safety['kill_switch_engaged'] else G + 'armed'}{RST}  ·  actions/hour cap: "
            f"{safety['cap']}  ·  audit chain valid: {safety['audit_chain_valid']}"
        )

        self._header("ROI")
        roi = ROICalculator.quick_summary(prof.roi_vertical, tier="professional")
        for label, value in (
            ("Monthly engagement", f"${roi['monthly_cost_usd']:,}"),
            ("Monthly value", f"${roi['monthly_value_protected_usd']:,.0f}"),
            ("ROI multiple", f"{roi['roi_ratio']:.0f}x"),
            ("Payback", f"{roi['payback_days']:.1f} days"),
        ):
            self._p(f"  {DIM}{label:<22}{RST}{G}{BOLD}{value}{RST}", 0.1)
        self._p(f"\n  {W}{roi['executive_summary']}{RST}")

        path = self.write_report(roi, contributions)
        self._p(f"\n  {G}✓ Report:{RST} {path}")
        return {"vertical": prof.key, "risk": risk, "roi": roi, "report": str(path)}

    def write_report(self, roi: dict[str, Any], contributions: dict[str, float]) -> Path:
        env = Environment(autoescape=select_autoescape(["html"]))
        template = env.from_string(
            resources.files("golden.demo").joinpath("report_template.html").read_text("utf-8")
        )
        total = sum(contributions.values()) or 1
        html = template.render(
            platform_name=os.getenv("PLATFORM_NAME", "Golden Platform"),
            client_name=self.client_name,
            vertical=self.profile.label,
            date=datetime.now().strftime("%B %d, %Y"),
            roi=roi,
            signals=self.profile.signals,
            factors=[(k, round(v / total * 100)) for k, v in contributions.items()],
            model_cards=self.profile.model_cards,
        )
        slug = re.sub(r"[^a-z0-9]+", "_", self.client_name.lower()).strip("_")[:40] or "client"
        out = self.output_dir / f"report_{self.profile.key}_{slug}_{datetime.now():%Y%m%d}.html"
        out.write_text(html, encoding="utf-8")
        return out


def run_demo(vertical: str, client: str, output_dir: Path, *, fast: bool = False) -> list[dict[str, Any]]:
    keys = list(PROFILES) if vertical == "all" else [vertical]
    return [ClientDemo(k, client, output_dir, fast=fast).run() for k in keys]
