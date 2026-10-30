"""``golden`` command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Literal

from golden import __version__
from golden.logging import configure_logging


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


# ----------------------------------------------------------------------------- commands
def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from golden.services.registry import SERVICES

    target, port = SERVICES[args.service]
    configure_logging(args.service)
    port = args.port or int(os.getenv("PORT", port))
    uvicorn.run(target, host=args.host, port=port, log_config=None, proxy_headers=True)
    return 0


def cmd_roi(args: argparse.Namespace) -> int:
    from golden.ai.business_value import ROICalculator

    result = ROICalculator.quick_summary(args.vertical, tier=args.tier)
    _print(
        result
        if args.json
        else {
            k: result[k]
            for k in (
                "vertical",
                "tier",
                "monthly_cost_usd",
                "monthly_value_protected_usd",
                "roi_ratio",
                "payback_days",
                "annual_net_benefit_usd",
                "executive_summary",
            )
        }
    )
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    from golden.ai.training import train_and_save

    configure_logging("trainer")
    kinds: list[Literal["lstm", "tcn"]] = ["lstm", "tcn"] if args.model == "all" else [args.model]
    for kind in kinds:
        result = train_and_save(kind, output_dir=args.output_dir, epochs=args.epochs, device=args.device)
        _print(result.__dict__)
    return 0


def cmd_orchestrate(args: argparse.Namespace) -> int:
    from golden.ai.agents import Orchestrator

    configure_logging("orchestrator")
    results = Orchestrator().run(cycles=args.cycles, interval=args.interval)
    if args.cycles:
        _print(
            [{"analysis": r["analysis"]["status"], "execution": r["execution"]["status"]} for r in results]
        )
    return 0


def cmd_demo_client(args: argparse.Namespace) -> int:
    from golden.demo.client_demo import run_demo

    run_demo(args.vertical, args.client, Path(args.output), fast=args.fast)
    return 0


def cmd_demo_engine(args: argparse.Namespace) -> int:
    from golden.ai.demo_run import run_demo

    _print(run_demo(epochs=args.epochs, output_dir=Path(args.output_dir)))
    return 0


def cmd_security_status(_: argparse.Namespace) -> int:
    from golden.security import security_status

    _print(security_status())
    return 0


def cmd_security_manifest(args: argparse.Namespace) -> int:
    from golden.security import write_manifest

    print(write_manifest(args.model_dir))
    return 0


def cmd_gpu_doctor(_: argparse.Namespace) -> int:
    from golden.ai.accel import device_report

    _print(device_report())
    return 0


def cmd_gpu_analyze(args: argparse.Namespace) -> int:
    from golden.gpu import analyze_fleet, collect_local, make_gpu_fleet

    samples = collect_local() if args.local else make_gpu_fleet(scenario=args.scenario)
    report = analyze_fleet(samples, on_prem=args.on_prem).to_dict()
    if not args.verbose:
        report.pop("findings")
    _print(report)
    return 0


def _inventory(path: str | None):
    from golden.migration import load_inventory, sample_inventory

    return load_inventory(path) if path else sample_inventory()


def cmd_migrate_assess(args: argparse.Namespace) -> int:
    from golden.migration import assess_inventory

    result = assess_inventory(_inventory(args.inventory), bandwidth_gbps=args.bandwidth_gbps)
    _print(result if args.verbose else result["summary"])
    return 0


def cmd_migrate_plan(args: argparse.Namespace) -> int:
    from golden.migration import plan_waves

    plan = plan_waves(_inventory(args.inventory), max_vms_per_wave=args.max_vms, max_tb_per_wave=args.max_tb)
    _print(plan.to_dict())
    return 0


def cmd_migrate_manifests(args: argparse.Namespace) -> int:
    from golden.migration import MappingConfig, plan_waves, write_wave_manifests

    vms = _inventory(args.inventory)
    plan = plan_waves(vms, max_vms_per_wave=args.max_vms, max_tb_per_wave=args.max_tb)
    cfg = MappingConfig(
        source_provider=args.source_provider,
        target_namespace=args.target_namespace,
        default_storage_class=args.storage_class,
    )
    files = write_wave_manifests(args.output, plan.waves, vms, cfg)
    _print({"waves": [w.name for w in plan.waves], "files": [str(f) for f in files], "backlog": plan.backlog})
    return 0


def _access_model(path: str | None):
    from golden.identity import load_model

    try:
        return load_model(path)
    except FileNotFoundError:
        if path:
            raise
        return None


def cmd_iam_model(args: argparse.Namespace) -> int:
    from golden.identity import lint_summary, load_model

    model = load_model(args.model)
    result = lint_summary(model)
    _print({**result, "group_map": model.group_map()} if args.verbose else result)
    return 0 if result["valid"] else 1


def cmd_iam_roles(args: argparse.Namespace) -> int:
    from golden.identity import analyze_authorization_details, sample_authorization_details

    details = (
        json.loads(Path(args.input).read_text(encoding="utf-8"))
        if args.input
        else sample_authorization_details()
    )
    result = analyze_authorization_details(
        details,
        unused_days=args.unused_days,
        org_accounts=set(args.org_accounts.split(",")) if args.org_accounts else None,
        model=_access_model(args.model),
    )
    if not args.verbose:
        result = {
            "summary": result["summary"],
            "consolidation": result["consolidation"],
            "actions": [
                {
                    k: r[k]
                    for k in ("account_id", "role", "disposition", "suggested_persona", "consolidate_into")
                }
                for r in result["roles"]
                if r["disposition"] not in {"keep", "managed"}
            ],
        }
    _print(result)
    return 0


def cmd_iam_gaps(args: argparse.Namespace) -> int:
    from golden.identity import assess_gaps, load_findings, sample_findings

    result = assess_gaps(load_findings(args.wiz) if args.wiz else sample_findings())
    if not args.verbose:
        result = {
            "summary": result["summary"],
            "register": [
                {k: r[k] for k in ("control", "title", "status", "open_findings", "layers", "remediation")}
                for r in result["register"]
            ],
        }
    _print(result)
    return 0


def cmd_iam_controls(_: argparse.Namespace) -> int:
    from golden.identity import catalog

    _print(catalog())
    return 0


def cmd_agent_run(args: argparse.Namespace) -> int:
    from dataclasses import replace

    from golden.agentops import SAMPLE_TASKS, SafeAgentRunner, SimulatedTaskAgent, load_identity

    ident = load_identity(args.agent)
    if args.per_run_usd:
        ident = replace(ident, per_run_usd=args.per_run_usd)
    if args.step_ceiling:
        ident = replace(ident, step_ceiling=args.step_ceiling)
    task = (
        json.loads(Path(args.input).read_text(encoding="utf-8")) if args.input else SAMPLE_TASKS[args.sample]
    )
    runner = SafeAgentRunner(
        ident,
        caps=not args.no_caps,
        loop_detection=not args.no_loop_detect,
        checkpoints=not args.no_checkpoint,
    )
    runner.drain.install()
    result = runner.run(SimulatedTaskAgent(ident.model), task, resume=args.resume).to_dict()
    if not args.verbose:
        result.pop("spans")
    _print(result)
    return 0 if result["result"] == "success" else 1


def cmd_agent_report(_: argparse.Namespace) -> int:
    from golden.agentops import RunLedger, unit_economics
    from golden.agentops.runner import state_dir_default

    _print(unit_economics(RunLedger(state_dir_default()).records()))
    return 0


def cmd_agent_verify(_: argparse.Namespace) -> int:
    from golden.agentops.proofs import verify_controls

    result = verify_controls()
    _print(result)
    return 0 if result["passed"] else 1


def cmd_agent_overnight(args: argparse.Namespace) -> int:
    from golden.agentops.proofs import overnight_projection

    _print(overnight_projection(sec_per_step=args.sec_per_step, workers=args.workers, hours=args.hours))
    return 0


def cmd_agent_redteam(args: argparse.Namespace) -> int:
    from golden.agentops import LLMGateway, run_redteam

    report = run_redteam(LLMGateway(), threshold=args.threshold).to_dict()
    _print(report)
    return 0 if report["gate"] == "pass" else 1


def cmd_llm_ask(args: argparse.Namespace) -> int:
    from golden.agentops import LLMGateway

    result = LLMGateway().complete(
        args.prompt, caller=args.caller, system=args.system, max_tokens=args.max_tokens
    )
    _print(result.to_dict())
    return 0 if result.status in {"success", "cache_hit"} else 1


def cmd_rag_ask(args: argparse.Namespace) -> int:
    from golden.ai.rag import RAGPipeline, sample_corpus

    rag = RAGPipeline()
    sources = [Path(p) for p in args.docs] if args.docs else []
    if sources:
        for path in sources:
            files = sorted(path.rglob("*.md")) if path.is_dir() else [path]
            for f in files:
                rag.ingest(f.read_text(encoding="utf-8"), str(f))
    else:
        rag.ingest(sample_corpus(), "sample_kb")
    _print(rag.ask(args.question))
    return 0


def _fraud_frames(args: argparse.Namespace):
    from golden.ai.datasets.fintech_simulator import make_fraud_scenario_stream

    baseline = make_fraud_scenario_stream(args.baseline_rows, seed=1)
    current = make_fraud_scenario_stream(args.current_rows, scenario=args.scenario, seed=args.seed)
    return baseline, current


def cmd_model_drift(args: argparse.Namespace) -> int:
    from golden.ai.lifecycle import check_drift

    result = check_drift(*_fraud_frames(args))
    _print(result)
    return 2 if result["drifted"] else 0


def cmd_model_retrain(args: argparse.Namespace) -> int:
    from golden.ai.lifecycle import retrain_if_drifted

    result = retrain_if_drifted(*_fraud_frames(args), root=args.registry, force=args.force)
    _print(result)
    return 1 if result["action"] == "rejected" else 0


def cmd_model_promote(args: argparse.Namespace) -> int:
    from golden.ai.lifecycle import DEFAULT_GATES, MODEL_NAME, ModelRegistry
    from golden.ai.lifecycle.registry import PromotionRejected

    try:
        result = ModelRegistry(args.registry).promote(
            MODEL_NAME,
            args.version,
            gates=DEFAULT_GATES,
            primary_metric="recall",
            approver=args.approver,
            tolerance=args.tolerance,
        )
    except PromotionRejected as exc:
        # A refused promotion is an expected outcome, not a crash: report it and exit 3.
        _print({"model": MODEL_NAME, "version": args.version, "promoted": False, "reason": str(exc)})
        return 3
    _print(result)
    return 0


def cmd_model_rollback(args: argparse.Namespace) -> int:
    from golden.ai.lifecycle import MODEL_NAME, ModelRegistry

    _print(ModelRegistry(args.registry).rollback(MODEL_NAME, approver=args.approver))
    return 0


def cmd_model_list(args: argparse.Namespace) -> int:
    from golden.ai.lifecycle import MODEL_NAME, ModelRegistry

    reg = ModelRegistry(args.registry)
    _print({"aliases": reg.aliases(MODEL_NAME), "versions": [v.to_dict() for v in reg.versions(MODEL_NAME)]})
    return 0


def _kv(pairs: list[str] | None) -> dict[str, float] | None:
    if not pairs:
        return None
    out: dict[str, float] = {}
    for pair in pairs:
        name, _, value = pair.partition("=")
        out[name] = float(value)
    return out


def cmd_finops_report(args: argparse.Namespace) -> int:
    from datetime import date

    from golden.finops import finops_report

    _print(
        finops_report(
            args.input,
            key=args.key,
            budgets=_kv(args.budget),
            usage=_kv(args.usage),
            unit=args.unit,
            method=args.method,
            as_of=date.fromisoformat(args.as_of) if args.as_of else None,
        )
    )
    return 0


def _focus_frame(path: str | None):
    from golden.finops import load_focus, sample_focus_data

    return load_focus(path) if path else sample_focus_data()


def cmd_finops_anomalies(args: argparse.Namespace) -> int:
    from golden.finops import detect_anomalies

    found = detect_anomalies(
        _focus_frame(args.input), by=args.by, threshold=args.threshold, min_impact=args.min_impact
    )
    _print([a.to_dict() for a in found])
    return 0


def cmd_finops_coverage(args: argparse.Namespace) -> int:
    from golden.finops import tag_coverage

    _print(tag_coverage(_focus_frame(args.input)).to_dict())
    return 0


def cmd_finops_k8s(_: argparse.Namespace) -> int:
    from golden.finops import allocate_cluster_cost, sample_cluster

    _print(allocate_cluster_cost(*sample_cluster()).to_dict())
    return 0


def cmd_finops_sample(args: argparse.Namespace) -> int:
    from golden.finops import sample_focus_data, to_focus_csv

    to_focus_csv(sample_focus_data(), args.out)
    print(args.out)
    return 0


def cmd_gpu_partition(args: argparse.Namespace) -> int:
    import yaml

    from golden.gpu import Workload, plan_partitioning

    raw = (
        yaml.safe_load(Path(args.workloads).read_text(encoding="utf-8"))
        if args.workloads
        else [
            {
                "name": "fraud-scoring",
                "memory_gb": 8,
                "compute_fraction": 0.1,
                "isolation_required": True,
                "tenant": "fin",
            },
            {
                "name": "triage-llm",
                "memory_gb": 18,
                "compute_fraction": 0.3,
                "isolation_required": True,
                "tenant": "health",
            },
            {"name": "embeddings", "memory_gb": 4, "compute_fraction": 0.05, "bursty": True, "tenant": "fin"},
            {
                "name": "notebook",
                "memory_gb": 9,
                "compute_fraction": 0.15,
                "bursty": True,
                "tenant": "research",
            },
            {
                "name": "fine-tune",
                "memory_gb": 70,
                "compute_fraction": 1.0,
                "kind": "training",
                "tenant": "research",
            },
        ]
    )
    plan = plan_partitioning([Workload(**w) for w in raw], args.gpu, price_per_gpu_hour=args.price)
    _print(plan.to_dict())
    return 0


def cmd_features_demo(args: argparse.Namespace) -> int:
    from golden.ai.datasets.fintech_simulator import make_fraud_scenario_stream
    from golden.ai.features.store import ACCOUNT_TXN_VIEW, fintech_feature_store

    store = fintech_feature_store(make_fraud_scenario_stream(args.transactions, seed=11))
    end = store.offline.read(ACCOUNT_TXN_VIEW)["event_timestamp"].max()
    loaded = store.materialize_incremental(ACCOUNT_TXN_VIEW.name, end)
    report = store.check_skew(ACCOUNT_TXN_VIEW.name, as_of=end, sample=50)
    _print(
        {
            "materialized_entities": loaded,
            "skew": {
                "view": report.view,
                "as_of": str(report.as_of),
                "keys_checked": report.keys_checked,
                "mismatch_rate": report.mismatch_rate,
                "ok": report.ok,
                "mismatches": report.mismatches[:10],
            },
        }
    )
    return 0 if report.ok else 1


def cmd_migrate_portfolio(args: argparse.Namespace) -> int:
    from golden.migration import assess_portfolio, assess_vm, load_portfolio_csv, sample_portfolio

    apps = load_portfolio_csv(args.portfolio) if args.portfolio else sample_portfolio()
    result = assess_portfolio(apps, [assess_vm(v) for v in _inventory(args.inventory)])
    _print(result if args.verbose else result["summary"])
    return 0


def cmd_migrate_databases(args: argparse.Namespace) -> int:
    from golden.migration import Database, assess_databases, sample_databases

    dbs = (
        [Database.from_dict(d) for d in json.loads(Path(args.databases).read_text(encoding="utf-8"))]
        if args.databases
        else sample_databases()
    )
    result = assess_databases(dbs, bandwidth_gbps=args.bandwidth_gbps, platform=args.platform)
    _print(result if args.verbose else result["summary"])
    return 0


def cmd_iam_multicloud(args: argparse.Namespace) -> int:
    from golden.identity import multicloud_summary

    result = multicloud_summary(args.aws, args.azure, args.gcp)
    _print(result)
    return 0 if result.get("valid", True) else 1


def cmd_iam_matrix(args: argparse.Namespace) -> int:
    from golden.identity.multicloud import load_all, persona_matrix

    _print(persona_matrix(*load_all(args.aws, args.azure, args.gcp)))
    return 0


def _db_exit(report: object) -> int:
    """Non-zero when the analysis found anything critical, so `golden db` can gate CI."""
    from golden.database import severity_counts

    return 1 if severity_counts(getattr(report, "findings", [])).get("critical", 0) else 0


def cmd_db_workload(args: argparse.Namespace) -> int:
    from golden.database import analyse_workload, load_statements, parse_statements, sample_statements

    stats = load_statements(args.file) if args.file else parse_statements(sample_statements())
    report = analyse_workload(stats, top_n=args.top)
    _print(report.to_dict())
    return _db_exit(report)


def cmd_db_explain(args: argparse.Namespace) -> int:
    from golden.database import analyse_plan, load_plan, sample_explain_plans

    plan = load_plan(args.file) if args.file else sample_explain_plans()[args.scenario]
    report = analyse_plan(plan)
    _print(report.to_dict())
    return _db_exit(report)


def cmd_db_indexes(args: argparse.Namespace) -> int:
    from golden.database import analyse_indexes, sample_index_snapshot

    snap = json.loads(Path(args.file).read_text(encoding="utf-8")) if args.file else sample_index_snapshot()
    report = analyse_indexes(snap)
    _print(report.to_dict())
    return _db_exit(report)


def cmd_db_capacity(args: argparse.Namespace) -> int:
    from golden.database import assess_capacity, load_price_table, sample_capacity_profile

    profile = (
        json.loads(Path(args.file).read_text(encoding="utf-8")) if args.file else sample_capacity_profile()
    )
    report = assess_capacity(profile, price_table=load_price_table(args.prices) if args.prices else None)
    _print(report.to_dict())
    return _db_exit(report)


def cmd_config_get(args: argparse.Namespace) -> int:
    from golden import platform_config

    value = platform_config.get(args.key, platform_config.load(args.file))
    print(
        " ".join(map(str, value))
        if isinstance(value, list)
        else str(value).lower()
        if isinstance(value, bool)
        else value
    )
    return 0


def cmd_config_show(args: argparse.Namespace) -> int:
    from golden import platform_config

    _print(platform_config.load(args.file))
    return 0


# ----------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    from golden.services.registry import SERVICES

    p = argparse.ArgumentParser(
        prog="golden", description="Golden Platform — enterprise modernization template"
    )
    p.add_argument("--version", action="version", version=f"golden {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("serve", help="run a platform service")
    s.add_argument("service", choices=sorted(SERVICES))
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int)
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("roi", help="compute engagement ROI for a vertical")
    s.add_argument("--vertical", choices=["healthcare", "fintech", "gpu", "migration"], default="healthcare")
    s.add_argument("--tier", choices=["starter", "professional", "enterprise"], default="professional")
    s.add_argument("--json", action="store_true", help="full JSON including breakdown/details")
    s.set_defaults(func=cmd_roi)

    s = sub.add_parser("train", help="train SLI forecasters (requires the [ml] extra; uses GPU if present)")
    s.add_argument("--model", choices=["lstm", "tcn", "all"], default="all")
    s.add_argument("--epochs", type=int, default=3)
    s.add_argument("--output-dir", default="models")
    s.add_argument("--device", choices=["auto", "cuda", "mps", "cpu"], default=None)
    s.set_defaults(func=cmd_train)

    s = sub.add_parser("orchestrate", help="run the governed observe→analyze→plan→execute loop")
    s.add_argument("--cycles", type=int, default=None, help="number of cycles (default: run forever)")
    s.add_argument("--interval", type=float, default=None)
    s.set_defaults(func=cmd_orchestrate)

    demo = sub.add_parser("demo", help="demos").add_subparsers(dest="demo", required=True)
    s = demo.add_parser("client", help="narrated executive demo + HTML report")
    s.add_argument("--vertical", choices=["hospital", "bank", "gpu", "migration", "all"], default="hospital")
    s.add_argument("--client", default="Demo Client")
    s.add_argument("--output", default="demo_output")
    s.add_argument("--fast", action="store_true", help="no animation delays")
    s.set_defaults(func=cmd_demo_client)
    s = demo.add_parser("engine", help="end-to-end AI engine demo (train → infer → explain)")
    s.add_argument("--epochs", type=int, default=1)
    s.add_argument("--output-dir", default=".artifacts/demo")
    s.set_defaults(func=cmd_demo_engine)

    cfg = sub.add_parser("config", help="read platform.yaml").add_subparsers(dest="config", required=True)
    s = cfg.add_parser("get", help="print one value, e.g. cloud.provider")
    s.add_argument("key")
    s.add_argument("--file", default=None)
    s.set_defaults(func=cmd_config_get)
    s = cfg.add_parser("show", help="print the merged, validated configuration")
    s.add_argument("--file", default=None)
    s.set_defaults(func=cmd_config_show)

    sec = sub.add_parser("security", help="AI-safety controls").add_subparsers(dest="security", required=True)
    sec.add_parser("status", help="autonomy mode, kill switch, caps, audit chain").set_defaults(
        func=cmd_security_status
    )
    s = sec.add_parser("manifest", help="(re)write the SHA-256 model manifest")
    s.add_argument("--model-dir", default="models")
    s.set_defaults(func=cmd_security_manifest)

    gpu = sub.add_parser("gpu", help="GPU domain").add_subparsers(dest="gpu", required=True)
    gpu.add_parser("doctor", help="report available accelerators").set_defaults(func=cmd_gpu_doctor)
    s = gpu.add_parser("analyze", help="analyze a GPU fleet (simulated or local nvidia-smi)")
    s.add_argument("--scenario", choices=["typical", "hot", "efficient"], default="typical")
    s.add_argument("--local", action="store_true")
    s.add_argument("--on-prem", action="store_true")
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(func=cmd_gpu_analyze)
    s = gpu.add_parser("partition", help="plan MIG / time-slicing / MPS / whole-GPU for workloads")
    s.add_argument("--gpu", default="A100-80GB", help="A100-40GB | A100-80GB | H100-80GB")
    s.add_argument("--price", type=float, default=4.0, help="$ per GPU-hour (assumption)")
    s.add_argument("--workloads", help="YAML list of Workload fields (default: sample)")
    s.set_defaults(func=cmd_gpu_partition)

    mig = sub.add_parser("migrate", help="VMware → OpenShift migration").add_subparsers(
        dest="migrate", required=True
    )
    for name, func, helptext in (
        ("assess", cmd_migrate_assess, "assess migration readiness"),
        ("plan", cmd_migrate_plan, "plan migration waves"),
        ("manifests", cmd_migrate_manifests, "generate MTV manifests per wave"),
    ):
        s = mig.add_parser(name, help=helptext)
        s.add_argument("--inventory", help="RVTools vInfo CSV, RVTools export dir, or JSON (default: sample)")
        s.add_argument("--verbose", action="store_true")
        s.add_argument("--bandwidth-gbps", type=float, default=10.0)
        s.add_argument("--max-vms", type=int, default=50)
        s.add_argument("--max-tb", type=float, default=20.0)
        s.add_argument("--output", default="deploy/openshift/virtualization/waves")
        s.add_argument("--source-provider", default="vsphere-prod")
        s.add_argument("--target-namespace", default="migrated-vms")
        s.add_argument("--storage-class", default="ocs-storagecluster-ceph-rbd-virtualization")
        s.set_defaults(func=func)
    s = mig.add_parser("portfolio", help="7 Rs / TIME portfolio rationalization (uses VM assessment)")
    s.add_argument("--portfolio", help="applications CSV (default: sample)")
    s.add_argument("--inventory", help="RVTools export for rehost feasibility (default: sample)")
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(func=cmd_migrate_portfolio)
    s = mig.add_parser("databases", help="database migration assessment: target, strategy, CDC, cutover")
    s.add_argument("--databases", help="JSON list of Database fields (default: sample)")
    s.add_argument("--bandwidth-gbps", type=float, default=1.0)
    s.add_argument("--platform", choices=["aws", "openshift"], default="aws")
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(func=cmd_migrate_databases)

    iam = sub.add_parser(
        "iam", help="AWS IAM modernization (Identity Center, SCP/RCP, boundaries, Wiz)"
    ).add_subparsers(dest="iam", required=True)
    s = iam.add_parser("model", help="lint the persona access model (security/identity/access-model.yaml)")
    s.add_argument("--model", help="access model path (default: GOLDEN_ACCESS_MODEL or the repo file)")
    s.add_argument("--verbose", action="store_true", help="include the AD group -> permission set map")
    s.set_defaults(func=cmd_iam_model)
    s = iam.add_parser("roles", help="role cleanup / consolidation / Identity Center migration plan")
    s.add_argument(
        "--input", help="`aws iam get-account-authorization-details` JSON (default: sample estate)"
    )
    s.add_argument("--model", help="access model path, for persona matching")
    s.add_argument("--unused-days", type=int, default=90)
    s.add_argument("--org-accounts", help="comma-separated account IDs inside the organization")
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(func=cmd_iam_roles)
    s = iam.add_parser("gaps", help="Wiz findings -> control gap register")
    s.add_argument("--wiz", help="Wiz issues export (CSV, or GraphQL JSON) (default: sample findings)")
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(func=cmd_iam_gaps)
    iam.add_parser("controls", help="print the control-placement catalog").set_defaults(func=cmd_iam_controls)
    for name, func, helptext in (
        ("multicloud", cmd_iam_multicloud, "lint AWS + Azure + GCP access models and compare personas"),
        ("matrix", cmd_iam_matrix, "persona -> AWS permission set / Azure role / GCP role matrix"),
    ):
        s = iam.add_parser(name, help=helptext)
        s.add_argument("--aws")
        s.add_argument("--azure")
        s.add_argument("--gcp")
        s.set_defaults(func=func)

    from golden.network.cli import register as register_network

    register_network(sub)

    fin = sub.add_parser(
        "finops", help="FinOps: FOCUS showback/chargeback, anomalies, k8s cost"
    ).add_subparsers(dest="finops_cmd", required=True)
    s = fin.add_parser("report", help="showback/chargeback, coverage, anomalies, forecast, recommendations")
    s.add_argument("--input", help="FOCUS (or AWS CUR / Azure / GCP export) CSV; default: sample data")
    s.add_argument("--key", default="Team")
    s.add_argument("--method", choices=["proportional", "even", "fixed"], default="proportional")
    s.add_argument("--budget", action="append", help="NAME=AMOUNT (repeatable)")
    s.add_argument("--usage", action="append", help="NAME=UNITS (repeatable), for unit economics")
    s.add_argument("--unit", default="transactions")
    s.add_argument("--as-of", help="YYYY-MM-DD")
    s.set_defaults(func=cmd_finops_report)
    s = fin.add_parser("anomalies", help="daily cost anomalies (robust z-score)")
    s.add_argument("--input")
    s.add_argument("--by", default="ServiceName")
    s.add_argument("--threshold", type=float, default=3.5)
    s.add_argument("--min-impact", type=float, default=25.0)
    s.set_defaults(func=cmd_finops_anomalies)
    s = fin.add_parser("coverage", help="tag coverage of spend")
    s.add_argument("--input")
    s.set_defaults(func=cmd_finops_coverage)
    fin.add_parser("k8s", help="OpenCost-style namespace cost allocation (sample cluster)").set_defaults(
        func=cmd_finops_k8s
    )
    s = fin.add_parser("sample", help="write sample FOCUS data")
    s.add_argument("--out", default="focus-sample.csv")
    s.set_defaults(func=cmd_finops_sample)

    db = sub.add_parser(
        "db", help="database performance: workload, EXPLAIN, indexes, capacity"
    ).add_subparsers(dest="db_cmd", required=True)
    for name, func, helptext, input_help in (
        (
            "workload",
            cmd_db_workload,
            "top queries, cache hit, N+1, temp spills",
            "pg_stat_statements CSV/JSON",
        ),
        (
            "explain",
            cmd_db_explain,
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) findings + fixes",
            "EXPLAIN JSON",
        ),
        (
            "indexes",
            cmd_db_indexes,
            "unused/duplicate/missing indexes, bloat, autovacuum, wraparound",
            "catalog JSON",
        ),
        (
            "capacity",
            cmd_db_capacity,
            "pool sizing, memory, replicas, partitioning, rightsizing",
            "profile JSON",
        ),
    ):
        s = db.add_parser(name, help=helptext)
        s.add_argument(
            "file", nargs="?", help=f"{input_help} (default: built-in sample with planted problems)"
        )
        if name == "workload":
            s.add_argument("--top", type=int, default=10)
        if name == "explain":
            s.add_argument(
                "--scenario",
                default="refund_join",
                choices=[
                    "email_lookup",
                    "merchant_status",
                    "settlement_report",
                    "refund_join",
                    "bitmap_lossy",
                    "ledger_hash_join",
                    "healthy",
                ],
            )
        if name == "capacity":
            s.add_argument("--prices", help="price table YAML (default: illustrative sample)")
        s.set_defaults(func=func)

    feat = sub.add_parser("features", help="feature store").add_subparsers(dest="features_cmd", required=True)
    s = feat.add_parser(
        "demo", help="point-in-time features → materialize online → training/serving skew check"
    )
    s.add_argument("--transactions", type=int, default=600)
    s.set_defaults(func=cmd_features_demo)

    agent = sub.add_parser(
        "agent", help="AI agent operations (cost, loops, checkpoints, red-team)"
    ).add_subparsers(dest="agent_cmd", required=True)
    s = agent.add_parser("run", help="run an agent inside the safe runner (simulated model)")
    s.add_argument("--agent", default="invoice-reader")
    s.add_argument("--sample", choices=["good", "malformed", "stuck", "drifting"], default="good")
    s.add_argument("--input", help="task JSON file (overrides --sample)")
    s.add_argument("--resume", action="store_true")
    s.add_argument("--per-run-usd", type=float)
    s.add_argument("--step-ceiling", type=int)
    s.add_argument("--no-caps", action="store_true")
    s.add_argument("--no-loop-detect", action="store_true")
    s.add_argument("--no-checkpoint", action="store_true")
    s.add_argument("--verbose", action="store_true", help="include per-step trace spans")
    s.set_defaults(func=cmd_agent_run)
    agent.add_parser("report", help="unit economics from the run ledger").set_defaults(func=cmd_agent_report)
    agent.add_parser("verify", help="prove each cost control by turning it off, then on").set_defaults(
        func=cmd_agent_verify
    )
    s = agent.add_parser("overnight", help="what an unguarded looping fleet would cost overnight")
    s.add_argument("--sec-per-step", type=float, default=3.0)
    s.add_argument("--workers", type=int, default=12)
    s.add_argument("--hours", type=float, default=9.5)
    s.set_defaults(func=cmd_agent_overnight)
    s = agent.add_parser("redteam", help="run the red-team probe suite against the LLM gateway (gate)")
    s.add_argument("--threshold", type=float, default=1.0)
    s.set_defaults(func=cmd_agent_redteam)

    s = (
        sub.add_parser("llm", help="LLM gateway")
        .add_subparsers(dest="llm_cmd", required=True)
        .add_parser(
            "ask",
            help="one guarded, budgeted, cached LLM call (simulated unless GOLDEN_LLM_PROVIDER=anthropic)",
        )
    )
    s.add_argument("prompt")
    s.add_argument("--caller", default="cli")
    s.add_argument("--system", default="")
    s.add_argument("--max-tokens", type=int, default=512)
    s.set_defaults(func=cmd_llm_ask)

    s = (
        sub.add_parser("rag", help="retrieval-augmented Q&A")
        .add_subparsers(dest="rag_cmd", required=True)
        .add_parser("ask", help="answer from documents with citations (default: built-in sample policies)")
    )
    s.add_argument("question")
    s.add_argument("--docs", nargs="*", help="markdown files or directories to index")
    s.set_defaults(func=cmd_rag_ask)

    model = sub.add_parser("model", help="ML lifecycle: drift, retrain, promote, rollback").add_subparsers(
        dest="model_cmd", required=True
    )
    for name, func, helptext in (
        ("drift", cmd_model_drift, "PSI + KS drift of current vs baseline (exit 2 on drift)"),
        ("retrain", cmd_model_retrain, "retrain on drift; register as challenger if it passes the gate"),
    ):
        s = model.add_parser(name, help=helptext)
        s.add_argument("--registry", default="models/registry")
        s.add_argument("--baseline-rows", type=int, default=4000)
        s.add_argument("--current-rows", type=int, default=1500)
        s.add_argument("--scenario", choices=["clean", "mixed", "fraud_burst"], default="fraud_burst")
        s.add_argument("--seed", type=int, default=2)
        s.add_argument("--force", action="store_true")
        s.set_defaults(func=func)
    s = model.add_parser("promote", help="promote a version to champion (gates + named approver)")
    s.add_argument("version", type=int)
    s.add_argument("--approver", required=True)
    s.add_argument("--tolerance", type=float, default=0.0)
    s.add_argument("--registry", default="models/registry")
    s.set_defaults(func=cmd_model_promote)
    s = model.add_parser("rollback", help="move champion back to the previous version")
    s.add_argument("--approver", required=True)
    s.add_argument("--registry", default="models/registry")
    s.set_defaults(func=cmd_model_rollback)
    s = model.add_parser("list", help="registered versions and aliases")
    s.add_argument("--registry", default="models/registry")
    s.set_defaults(func=cmd_model_list)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
